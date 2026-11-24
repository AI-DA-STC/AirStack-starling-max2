#!/usr/bin/env python
"""STE task L0.13 Does tier 2 train at all? (PLAN.md section 4 row L0.13; LEAD CALL 21 Nov 2026): the L0.12 Guard recipe
trained on tier 2 (the Isaac Lab rigid-body Starling) beside a fresh tier 1 control with the same number of games at
once, game-steps, seed and procedure; both scored on T44's starts. Logic: ``source/svg_training/ste/tier2_train.py``;
trainer: ``ste/exploit_train.py``; settings, controls and the verdict: ``configs/ste_l013/gates.toml``.

Two jobs, two run folders, arm t1 first (t2 scores t1's networks on tier 2, so it names t1's finished folder):

    # arm t1, tier 1 (no Isaac):
    scripts/ste_job.py launch --task L0.13 --name l013_t1 --run-dir runs/<date>_ste_l013_t1 --min-s 600 --gpu-h 0.75 -- \\
        <python> scripts/ste_tier2_l013.py --arm t1 --run-dir runs/<date>_ste_l013_t1 --cap-h 0.75
    # arm t2, tier 2, after nvidia-smi and scripts/isaac_preflight.sh --approved-headless (exit 0), alone on the GPU:
    scripts/ste_job.py launch --task L0.13 --name l013_t2 --run-dir runs/<date>_ste_l013_t2 --min-s 1800 --gpu-h 2.5 -- \\
        <python> scripts/ste_tier2_l013.py --arm t2 --run-dir runs/<date>_ste_l013_t2 --t1-run runs/<date>_ste_l013_t1 \\
        --cap-h 2.5 --headless
    # the verdict over the two arms (CPU, seconds):
    ste_tier2_l013.py verdict --t1-run runs/<date>_ste_l013_t1 --t2-run runs/<date>_ste_l013_t2 --out runs/<date>_ste_l013_verdict

Arm t2's process starts Isaac Sim headless before torch is imported and leaves through ``os._exit`` (L0.3's shape: the
run contract lives in the process that trains, so a stop or the cap reserve acts at an update boundary); its checks that
need no Isaac (``--headless``, the t1 folder, a terminal folder) run first, from the standard library.

Run contract (``ste/run_contract.py``): the same command resumes from the last update boundary (networks, optimisers,
scalers, counters, the torch random state; the training games restart afresh); SIGINT or SIGTERM stops at the next tick
or update boundary with a checkpoint (exit 4); the cap is effective seconds (wall clock less the owner's pauses of this
process) = --cap-h x 3600 = the arm's [arms] cap_h. Training stops while the cap left is below the reserve for the final
phase plus room for the next update (and its curve read); curve reads and the final phase are never cut by the cap (only
SIGINT/SIGTERM), so an arm that is slow still finishes, with ``budget_reached`` false (TOO_SLOW, a result). Exit codes: 0
done; 2 refused (bad gate file, a pinned file changed, the gate file changed since the first launch, cap, device or job
mismatch, the t1 folder not finished, no --headless for t2, run folder busy); 3 cap (only before training: the controls
batch); 4 stopped on request; 5 a non-finite action, loss or weight (no retry; nothing saved over the last good
checkpoint); 6 CONTROL_FAILED (a control with a known answer failed: terminal, the same command ends with 6 again). The
waiter (``scripts/ste_job.py wait``) adds 20 ENDED_EARLY and 21 DIED.

One arm, in order: (t2: the Isaac world of [trainer] num_games x 6 drones and control C-1a on it and on the evaluation
view, every launch) the controls batches before training (tier 1, and tier 2 for t2: the untrained exploiter and the
parked Guard on T44's first eval_games starts); training, one line per update in ``train_log.jsonl``, a snapshot of the
networks per update (``snapshots/``), a curve read every curve_every_updates (``curve.json``); the final batches, the
controls again, ``agent_final.pt``, the clips (``videos/``, 2-D with the height panel) and ``results.json`` (last) /
``results.md``. ``--dry-cpu`` (tests only, never of record): CPU, tier 2 on the PyTorch reference world.
Observed in the training simulator; nothing here is a flight result."""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import shutil
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

HOUR_S = 3600.0
PINNED_SHA, GATES_COPY, CONTROLS_FILE = "gates.sha256", "gates.toml", "controls.json"
TRAIN_LOG, CURVE, RESULTS, AGENT_FINAL, RUN_FILE = "train_log.jsonl", "curve.json", "results.json", "agent_final.pt", "run.json"
SNAPSHOTS, INFO_FILE = "snapshots", "info.json"
PASS, FAIL, NONFINITE = "PASS", "FAIL", "NONFINITE"
ARMS = ("t1", "t2")
SIMULATOR = {1: ("training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, "
                 "fitted PX4 response, exploratory); study tag on (P1, PROPOSED)"),
             2: ("training simulator, tier 2 (the same command chain driving the Isaac Lab 2.3.2 rigid-body Starling in "
                 "PhysX); study tag on (P1, PROPOSED)")}


def say(text: str) -> None:
    print(f"[l013] {text}", flush=True)


def refuse(text: str) -> int:
    print(f"refused: {text}", file=sys.stderr, flush=True)
    return 2


def parser(isaac: bool = False) -> argparse.ArgumentParser:
    """The command line of one arm; ``isaac`` leaves out --headless (Isaac Lab's launcher adds its own)."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--arm", choices=ARMS, required=True)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--cap-h", type=float, required=True, help="cap in effective hours (= the launcher's --gpu-h)")
    ap.add_argument("--gates", type=Path, default=None, help="gate file (default configs/ste_l013/gates.toml; a resume "
                    "reads the run folder's pinned copy)")
    ap.add_argument("--t1-run", type=Path, help="arm t2: the finished arm t1 folder")
    ap.add_argument("--expect-gates-sha256", help="refuse unless the gate file has this sha256")
    ap.add_argument("--no-videos", action="store_true", help="skip the clips (tests only)")
    ap.add_argument("--dry-cpu", action="store_true", help="tests only: CPU, tier 2 on the PyTorch reference world; "
                    "never of record")
    ap.add_argument("--allow-code-change", action="store_true",
                    help="resume although the code differs from the first launch's (recorded in code.json)")
    if not isaac:
        ap.add_argument("--headless", action="store_true", help="arm t2: required (Isaac Lab)")
    return ap


def write_json(path: Path, obj) -> None:
    import ste_sweep_l011 as l011
    l011.write_json(path, obj)


def read_json(path: Path, default=None):
    return json.loads(Path(path).read_text()) if Path(path).is_file() else default


# ================================================================================================ pre-flight
def t1_problem(t1_run: Path | None, sha256: str | None = None) -> str | None:
    """Why arm t2 may not use ``t1_run`` (standard library only: it runs before Isaac starts), or None. The t1 folder
    must hold a complete results.json with every control PASS, made under the same gate file (when ``sha256`` is given)."""
    if t1_run is None:
        return "arm t2 names the finished arm t1 folder: --t1-run runs/<date>_ste_l013_t1"
    res = read_json(Path(t1_run) / RESULTS)
    if not res or res.get("complete") is not True or res.get("arm") != "t1":
        return f"{t1_run} holds no complete arm t1 {RESULTS}: run arm t1 first"
    if not res.get("controls_all_pass"):
        return f"{t1_run}: a control is not PASS"
    if sha256 is not None and res.get("gates_sha256") != sha256:
        return f"{t1_run} ran under gate sha256 {res.get('gates_sha256')}, this gate file is {sha256}"
    return None


def terminal_problem(run_dir: Path) -> tuple[int, str] | None:
    """(exit code, why) when the run folder ended for good: a non-finite value (5) or a failed control (6)."""
    controls = read_json(Path(run_dir) / CONTROLS_FILE, {})
    if any(v.get("status") == NONFINITE for v in controls.values()):
        return 5, f"a non-finite value was recorded in {run_dir / CONTROLS_FILE}: no retry (train-debug)"
    bad = [k for k, v in controls.items() if v.get("status") == FAIL]
    if bad:
        return 6, (f"control(s) {bad} failed in {run_dir / CONTROLS_FILE}: terminal, a new run needs a new run folder "
                   "(CONTROL_FAILED)")
    return None


def pre_isaac_problem(argv: list[str]) -> tuple[int, str] | None:
    """Arm t2 before Isaac Sim starts (CODING_PRACTICES section 8, standard library only): (exit code, why) or None."""
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--run-dir", type=Path)
    pre.add_argument("--t1-run", type=Path)
    known, _ = pre.parse_known_args(argv)
    if "--headless" not in argv:
        return 2, "arm t2 starts Isaac Lab: --headless (after scripts/isaac_preflight.sh --approved-headless)"
    why = t1_problem(known.t1_run)
    if why:
        return 2, why
    if known.run_dir is not None:
        return terminal_problem(known.run_dir)
    return None


def preflight(args: argparse.Namespace, gates, device: str) -> str | None:
    """The reason to refuse an arm, or None."""
    import torch

    from svg_training.ste import tier2_train as T
    problems = T.pin_problems(gates)
    if problems:
        return "pinned file(s) differ from the gate file: " + "; ".join(problems)
    if args.expect_gates_sha256 and args.expect_gates_sha256 != gates.sha256:
        return f"the gate file has sha256 {gates.sha256}, expected {args.expect_gates_sha256}"
    pinned = args.run_dir / PINNED_SHA
    if pinned.is_file() and pinned.read_text().strip() != gates.sha256:
        return (f"the gate file changed since the first launch in {args.run_dir}: a new limit means a new run folder")
    run = read_json(args.run_dir / RUN_FILE)
    if run and (run.get("arm") != args.arm or bool(run.get("dry_cpu")) != bool(args.dry_cpu)):
        return f"{args.run_dir} is arm {run.get('arm')} (dry {run.get('dry_cpu')}): one arm per run folder"
    if not (math.isfinite(args.cap_h) and args.cap_h > 0):
        return f"--cap-h must be a finite number of hours above 0, got {args.cap_h!r}"
    if abs(args.cap_h - float(gates.arms[args.arm]["cap_h"])) > 1e-9:
        return f"--cap-h {args.cap_h} differs from the gate file's [arms] {args.arm} cap_h {gates.arms[args.arm]['cap_h']}"
    job = read_json(args.run_dir / "job.json")
    if job:
        if abs(float(job.get("gpu_h", 0)) - args.cap_h) > 1e-9:
            return f"the launcher asked for {job.get('gpu_h')} GPU-h, --cap-h is {args.cap_h}: keep the two equal"
        if not str(device).startswith("cuda"):
            return f"a launched job with device {device!r}: runs of record play on the GPU (--dry-cpu is for tests)"
    if str(device).startswith("cuda") and not torch.cuda.is_available():
        return "the gate file plays on cuda and PyTorch sees no GPU"
    if args.arm == "t2":
        why = t1_problem(args.t1_run, gates.sha256)
        if why:
            return why
        if bool(read_json(args.t1_run / RUN_FILE, {}).get("dry_cpu")) != bool(args.dry_cpu):
            return f"{args.t1_run}: a dry CPU arm and a run of record never pair"
    return None


# ================================================================================================ the world
def isaac_world_factory(n: int, m: int, params, device: str):
    """IsaacWorld of n games x m drones (Isaac Sim already started), as scripts/train_standin.py and L0.2."""
    from svg_training.compat import isaaclab_232 as isaac
    sim = isaac.make_physics_sim(params.physics_dt_s, device)
    world = isaac.IsaacWorld(sim, n, m, params.airframe, params.physics_dt_s)
    isaac.physics_play(sim, world)
    return world


def torch_world_factory(n: int, m: int, params, device: str):
    from svg_training.ste import tier2_train as T
    return T.torch_world_factory(n, m, params, device)


# ================================================================================================ entry
def main(argv: list[str] | None = None, world_factory=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["verdict"]:
        return verdict_main(argv[1:])
    return run(parser().parse_args(argv), world_factory)


def run(args: argparse.Namespace, world_factory=None) -> int:
    import torch

    from svg_training.ste import atomic, tier2_train as T
    from svg_training.ste.run_contract import RunBusyError, RunGuard
    import ste_sweep_l011 as l011
    args.run_dir = args.run_dir.resolve()
    if args.t1_run is not None:
        args.t1_run = args.t1_run.resolve()
    if not args.dry_cpu and (ROOT / "runs").resolve() not in args.run_dir.parents:
        return refuse(f"{args.run_dir} is not under {ROOT / 'runs'}")
    if args.arm == "t2" and not (args.dry_cpu or getattr(args, "headless", True)):
        return refuse("arm t2 starts Isaac Lab: --headless (after scripts/isaac_preflight.sh --approved-headless)")
    src = args.run_dir / GATES_COPY if (args.run_dir / GATES_COPY).is_file() else (args.gates or T.GATES_FILE)
    try:
        gates = T.load_gates(src)
    except (OSError, ValueError) as err:
        return refuse(f"gate file {src}: {err}")
    if args.gates is not None and (args.run_dir / GATES_COPY).is_file() and T.sha256_file(args.gates) != gates.sha256:
        return refuse(f"--gates {args.gates} differs from the run folder's pinned copy: a new limit means a new run folder")
    device = "cpu" if args.dry_cpu else gates.run["device"]
    reason = preflight(args, gates, device)
    if reason:
        return refuse(reason)
    ended = terminal_problem(args.run_dir)
    if ended:
        print(ended[1], file=sys.stderr, flush=True)
        return ended[0]
    if world_factory is None:
        world_factory = torch_world_factory if args.dry_cpu else isaac_world_factory
    args.run_dir.mkdir(parents=True, exist_ok=True)
    try:
        with RunGuard(args.run_dir, cap_s=args.cap_h * HOUR_S, dump=torch.save,
                      load=lambda p: torch.load(p, weights_only=False)) as guard:
            changed = l011.pin_code(args)
            if changed:
                return refuse(changed)
            if not (args.run_dir / PINNED_SHA).is_file():
                shutil.copyfile(src, args.run_dir / GATES_COPY)
                atomic.write_text(args.run_dir / PINNED_SHA, gates.sha256 + "\n")
            if not (args.run_dir / RUN_FILE).is_file():
                write_json(args.run_dir / RUN_FILE, {
                    "arm": args.arm, "tier": T.TIERS[args.arm], "cap_h": args.cap_h, "dry_cpu": bool(args.dry_cpu),
                    "t1_run": None if args.t1_run is None else str(args.t1_run), "device": device})
            return Arm(gates, args, guard, device, world_factory).run()
    except RunBusyError as err:
        return refuse(str(err))


# ================================================================================================ one arm
class Arm:
    """One arm of L0.13 in its run folder (module docstring). The phases ("controls", "train", "final", "done") and
    the learner live in the run contract's checkpoint."""

    def __init__(self, gates, args, guard, device: str, world_factory):
        import torch

        from svg_training.core.physics_layer import load_game_physics_params
        from svg_training.ste import exploit, sweep, tier2_train as T
        self.T, self.exploit, self.sweep, self.torch = T, exploit, sweep, torch
        self.gates, self.args, self.guard, self.device = gates, args, guard, device
        self.arm, self.run_dir = args.arm, args.run_dir
        self.tier = T.TIERS[self.arm]
        self.cfg1, self.cfg2 = T.tier_cfg(gates, 1), T.tier_cfg(gates, 2)
        self.params = load_game_physics_params(self.cfg2)
        self.guards, self.strikes = sweep.parse_size(gates.run["size"])
        self.n_eval, self.ticks_cap = int(gates.run["eval_games"]), int(gates.run["ticks_cap"])
        self.hold = int(gates.trainer["decision_ticks"])
        self.ref = exploit.load_reference(T.ROOT / gates.reference["file"])
        self.world_factory = world_factory
        self.world = None
        self.opp, self.parked = gates.run["opponent"], gates.run["parked"]
        self.cells = [(T.EXPLOITER, self.opp), (self.parked, self.opp)]
        self.ticks_seen = 0

    # ------------------------------------------------------------------------------------------- small helpers
    def cfg(self, tier: int):
        return self.cfg1 if tier == 1 else self.cfg2

    def should_stop(self) -> bool:
        """Controls batch: SIGINT/SIGTERM every tick, the cap every cap_check_every_ticks ticks."""
        if self.guard.stop_requested:
            return True
        self.ticks_seen += 1
        return self.ticks_seen % int(self.gates.run["cap_check_every_ticks"]) == 0 and self.guard.cap_reached()

    def stop_final(self) -> bool:
        """Curve reads and the final phase: their time is reserved before each update; only SIGINT/SIGTERM stops them."""
        return self.guard.stop_requested

    def view(self, k: int):
        return self.T.view(self.world, k, self.params)

    def batch(self, tier: int, cells: list, team, stopper, players: dict | None = None) -> dict:
        """One evaluation batch on T44's first eval_games starts, on ``tier`` (tier 2: a view of the Isaac world)."""
        import numpy as np
        world = self.view(len(cells) * self.n_eval) if tier == 2 else None
        pg = self.exploit.play_cells(self.cfg(tier), self.gates.run["size"], self.ref, cells, self.n_eval, self.device,
                                     self.ref.meta["seed"], self.ticks_cap, learner=team, hold_ticks=self.hold,
                                     should_stop=stopper, world=world, players=players)
        pg["tier"] = np.full(len(pg["outcome"]), self.T.batch_tier(pg), dtype=np.int8)   # the tier each game RAN on
        return pg

    def per_cell(self, pg: dict, cells: list) -> dict:
        return {c: self.exploit.slice_cell(pg, k, self.n_eval) for k, c in enumerate(cells)}

    def holds(self, pg: dict) -> tuple[int, int]:
        """(holds, finished games) of a cell; the tier its games ran on is kept in ``counted_tier`` (QC T2: a count
        carries where it came from, so a tier 2 number read from a tier 1 batch is caught)."""
        c = self.exploit.counts(pg)
        self.counted_tier = tier_ran(pg) if "tier" in pg else None
        return c["holds"], c["games"]

    def refresh(self) -> None:
        """After an evaluation (both arms: one procedure): every training game restarts afresh, so a tier 2 view's
        writes never reach a training game (ste/tier2_train module docstring)."""
        env = self.learner.env
        self.learner.obs, _ = env.reset()
        self.learner.states = env.state()

    def save_controls(self, controls: dict) -> None:
        write_json(self.run_dir / CONTROLS_FILE, controls)

    def controls(self) -> dict:
        return read_json(self.run_dir / CONTROLS_FILE, {})

    def ending(self, controls: dict, where: str) -> int | None:
        statuses = {v["status"] for v in controls.values()}
        code = 5 if NONFINITE in statuses else 6 if FAIL in statuses else None
        if code is not None and (code == 5 or self.gates.controls["stop_on_fail"]):
            bad = [k for k, v in controls.items() if v["status"] != PASS]
            say(f"{'NON-FINITE' if code == 5 else 'CONTROL FAILED'} {where}: {bad}; nothing is published (exit {code})")
            self.save_controls(controls)
            write_md(self.run_dir, self.gates, self.arm, controls, None)
            return code
        return None

    def stop(self, reason: str) -> int:
        from svg_training.ste.run_contract import EXIT_FOR_STOP
        if self.state["phase"] != "controls":
            self.state["learner"] = self.learner.state()
        self.guard.save(self.learner.updates, self.state)
        say(f"stopped ({reason}) at update {self.learner.updates}, phase {self.state['phase']}; checkpoint saved; the same "
            f"command resumes")
        return EXIT_FOR_STOP.get(reason, 4)

    # ------------------------------------------------------------------------------------------- the learner
    def build_learner(self):
        from svg_training.opponents.scripted import make_strategy
        from svg_training.ste import exploit_train
        g, tr, seed = self.gates, self.gates.trainer, int(self.gates.run["train_seed"])
        n = int(tr["num_games"])
        cfg = self.cfg(self.tier)
        if float(tr["shaping_weight"]) != float(cfg.rewards.shaping_weight):
            raise ValueError("the game file's shaping_weight differs from [trainer] shaping_weight")
        game = exploit_train.TrainGame(cfg, n, self.guards, self.strikes, device=self.device, seed=seed,
                                       world=self.world if self.tier == 2 else None)
        opp = make_strategy(self.opp, "strike", cfg, n, self.device, seed + self.exploit.STRIKE_SEED_OFFSET)
        env = exploit_train.DecisionEnv(game, self.hold, g.run["side"], opp)
        return exploit_train.Learner(dict(tr), env, self.device, seed, g.planned_updates)

    def peer_team(self, update: int):
        """The t1 arm's networks at ``update`` (its snapshot), on this device; None when t1 has none."""
        from svg_training.ste import exploit_train
        path = self.args.t1_run / SNAPSHOTS / f"u{update:04d}.pt"
        if not path.is_file():
            return None
        snap = self.torch.load(path, weights_only=False)
        team = exploit_train.team_from_modules("guard", snap, list(self.gates.trainer["hidden"]), self.device)
        team.name = f"t1 arm networks, update {update}"
        return team

    # ------------------------------------------------------------------------------------------- the run
    def run(self) -> int:
        from svg_training.ste import exploit_train
        g = self.gates
        resumed = self.guard.load_latest()
        self.state = resumed.state if resumed is not None else {"phase": "controls", "train_s": 0.0, "launches": 0}
        if self.state["phase"] == "done":
            say(f"this run folder is done ({self.run_dir / RESULTS}); nothing to do")
            return 0
        self.state["launches"] = int(self.state.get("launches", 0)) + 1
        controls = self.controls()
        if self.tier == 2:
            t0 = time.perf_counter()
            n = int(g.trainer["num_games"])
            self.world = self.world_factory(n, self.guards + self.strikes, self.params, self.device)
            say(f"world: {getattr(self.world, 'label', type(self.world).__name__)}, {n} games x "
                f"{self.guards + self.strikes} drones ({time.perf_counter() - t0:.0f} s)")
            k = self.T.PEER_BATCH_CELLS * self.n_eval
            for name, size in ((f"ctl_physics_agreement_launch{self.state['launches']}", n),
                               (f"ctl_physics_agreement_view_launch{self.state['launches']}", k)):
                w = self.world if size == n else self.view(size)     # the view is built (its idle games parked) here
                a = self.T.physics_agreement(g, self.cfg2, w, self.device)
                controls[name] = {"status": PASS if a["pass"] else FAIL, "phase": "launch",
                                  "detail": f"{a['games']} games x {a['drones']} drones x {a['ticks']} ticks on {a['world']}: "
                                            f"largest gap {a['max_gap_m']:.5f} m (limit {a['limit_m']} m)", **a}
                say(f"{name}: {controls[name]['detail']}")
            code = self.ending(controls, "in the physics agreement check")
            if code is not None:
                return code
            self.save_controls(controls)
        self.learner = self.build_learner()
        motion = self.learner.env.game.motion
        diff = self.T.cfg_differences(self.cfg1, self.cfg2)
        ok = diff == list(g.controls["tier_difference"]) and (motion.startswith("physics/") == (self.tier == 2))
        controls["ctl_tier_difference"] = {"status": PASS if ok else FAIL, "phase": "launch",
                                           "detail": f"tier 1 v tier 2 settings differ in {diff}; the training game runs "
                                                     f"{motion!r} (tier {self.tier})"}
        code = self.ending(controls, "in the tier check")
        if code is not None:
            return code
        self.save_controls(controls)
        if "learner" in self.state:
            self.learner.load_state(self.state["learner"])
            say(f"resumed at update {self.learner.updates} ({self.learner.game_steps:,} game-steps), phase "
                f"{self.state['phase']}, launch {self.state['launches']}")
        else:
            say(f"fresh start: arm {self.arm} (tier {self.tier}), Guard v {self.opp}, {g.trainer['num_games']} games, "
                f"{g.planned_updates} updates planned ({g.planned_game_steps:,} game-steps); gate {g.sha256[:12]}")
        try:
            if self.state["phase"] == "controls":
                code = self.phase_controls()
                if code is not None:
                    return code
            if self.state["phase"] == "train":
                code = self.phase_train()
                if code is not None:
                    return code
            return self.phase_final()
        except exploit_train.NonFinite as err:
            say(f"NON-FINITE: {err}; nothing saved over the last good checkpoint (exit 5)")
            c = self.controls()
            c["no_nonfinite_training"] = {"status": NONFINITE, "phase": self.state["phase"], "detail": str(err)}
            self.save_controls(c)
            return 5

    # ------------------------------------------------------------------------------------------- 1. controls
    def phase_controls(self) -> int | None:
        import numpy as np
        g, ex, T = self.gates, self.exploit, self.T
        controls = self.controls()
        started = time.perf_counter()
        team = self.learner.team()
        try:
            pgs = {1: self.batch(1, self.cells, team, self.should_stop)}
            if self.tier == 2:
                pgs[2] = self.batch(2, self.cells, team, self.should_stop)
        except self.sweep.SweepStopped:
            return self.stop(self.guard.stop_reason() or "cap")
        self.state["batch_s"] = time.perf_counter() - started
        cap = self.ticks_cap
        before = {}
        for tier, pg in pgs.items():
            np.savez_compressed(self.run_dir / f"eval_before_t{tier}.npz",
                                **{k: v for k, v in pg.items() if isinstance(v, np.ndarray)})
            cp = self.per_cell(pg, self.cells)
            exp, parked = cp[self.cells[0]], cp[self.cells[1]]
            before[tier] = {"untrained": list(self.holds(exp)), "parked": list(self.holds(parked))}
            good, text = ex.replay_ok(exp, parked, self.device, g.controls)
            controls[f"ctl_untrained_is_still_t{tier}"] = {"status": PASS if good else FAIL, "phase": "before",
                                                           "detail": f"untrained exploiter v {self.parked}, tier {tier}: {text}"}
            controls.update(plumbing(ex, pg, self.ref, self.n_eval, "before", f"_t{tier}_before"))
            controls.update(batch_controls(T, pg, tier, "before", f"_t{tier}_before"))
        t44 = {k: v[:self.n_eval] for k, v in self.ref.cell(g.reference["variant"], self.parked, self.opp).items()}
        good, text = ex.replay_ok(self.per_cell(pgs[1], self.cells)[self.cells[1]], t44, self.device, g.controls,
                                  ticks_cap=cap)
        controls["ctl_reference_replay"] = {"status": PASS if good else FAIL, "phase": "before",
                                            "detail": f"tier 1 {self.parked} v {self.opp} replays T44: {text}"}
        if self.tier == 2:
            bar = T.trains_bar(tuple(before[2]["untrained"]), tuple(before[2]["parked"]))
            controls["ctl_negative_bar_t2"] = {"status": FAIL if bar["cleared"] else PASS, "phase": "before",
                                               "detail": f"untrained {before[2]['untrained']} v parked {before[2]['parked']} "
                                                         f"on tier 2: bar cleared {bar['cleared']} (must be False)"}
            info = read_json(self.run_dir / INFO_FILE, {})
            info["parked_t2_v_t44_tier1"] = {"t2": before[2]["parked"], "t44": list(self.holds(t44)),
                                             "note": "INFO: tier 2 is another drone; not a control"}
            write_json(self.run_dir / INFO_FILE, info)
        self.state["before"] = before
        (self.run_dir / SNAPSHOTS).mkdir(exist_ok=True)              # the start networks (the same in both arms)
        self.torch.save(T.snapshot(self.learner.modules()), self.run_dir / SNAPSHOTS / "u0000.pt")
        say("controls: " + ", ".join(f"{k} {v['status']}" for k, v in controls.items()))
        code = self.ending(controls, "before training")
        if code is not None:
            return code
        self.save_controls(controls)
        self.refresh()
        self.state["pre_s"] = self.guard.effective_s()       # QC C1: the effective seconds before the first update
        self.state["phase"] = "train"
        self.state["learner"] = self.learner.state()
        self.guard.save(self.learner.updates, self.state)
        return None

    # ------------------------------------------------------------------------------------------- 2. training
    def phase_train(self) -> int | None:
        g, T = self.gates, self.T
        planned = g.planned_updates
        curve = read_json(self.run_dir / CURVE, [])
        reserve = T.final_reserve_s(g, self.arm, float(self.state.get("batch_s", 0.0)))
        self.state["final_reserve_s"] = reserve
        (self.run_dir / SNAPSHOTS).mkdir(exist_ok=True)
        u = self.learner.updates           # a read stopped by SIGINT after its update's checkpoint is done on resume
        if u and T.curve_due(g, u) and not any(p["update"] == u for p in curve):
            code = self.curve_read(curve)
            if code is not None:
                return code
        while self.learner.updates < planned:
            if self.guard.stop_requested:
                return self.stop("interrupted")
            due = T.curve_due(g, self.learner.updates + 1)
            need = T.room_needed_s(g, reserve, self.state.get("last_update_s"), self.state.get("last_curve_s"), due)
            left = self.guard.cap_s - self.guard.effective_s()
            if left < need:
                self.state["train_stop"] = (f"cap reserve: {left:.0f} s left < {need:.0f} s needed (final reserve "
                                            f"{reserve:.0f} s + room for the next update) at update {self.learner.updates}")
                say(self.state["train_stop"])
                break
            reason = self.guard.stop_reason()
            if reason:
                return self.stop(reason)
            started = time.perf_counter()
            stats = self.learner.update()
            took = time.perf_counter() - started
            self.state["train_s"] = float(self.state.get("train_s", 0.0)) + took
            self.state["last_update_s"] = took
            line = {**stats, "seconds": took, "game_steps_per_s": stats["game_steps"] / took if took > 0 else None,
                    "effective_s": self.guard.effective_s(), "time": time.time(), "tier": self.tier,
                    "motion": self.learner.env.game.motion}
            with open(self.run_dir / TRAIN_LOG, "a") as f:
                f.write(json.dumps(line) + "\n")
            self.torch.save(T.snapshot(self.learner.modules()),
                            self.run_dir / SNAPSHOTS / f"u{self.learner.updates:04d}.pt")
            if self.learner.updates % int(g.trainer["checkpoint_every_updates"]) == 0:
                self.state["learner"] = self.learner.state()
                self.guard.save(self.learner.updates, self.state)
            if due:
                code = self.curve_read(curve)
                if code is not None:
                    return code
            say(f"update {self.learner.updates}/{planned}: {self.learner.game_steps:,} game-steps, "
                f"{line['game_steps_per_s'] or 0:,.0f} game-steps/s, {stats['games_ended']} games ended")
        if not curve or curve[-1]["update"] != self.learner.updates:
            code = self.curve_read(curve)
            if code is not None:
                return code
        self.state.setdefault("train_stop", f"budget: {self.learner.game_steps:,} game-steps in {self.learner.updates} "
                                            f"updates ({g.planned_game_steps:,} planned)")
        self.state["learner"] = self.learner.state()
        self.state["phase"] = "final"
        self.guard.save(self.learner.updates, self.state)
        return None

    def curve_read(self, curve: list) -> int | None:
        """The current networks on the curve starts (never the scoring starts): t1 on tier 1; t2 on tier 2 and tier 1,
        and t1's networks of the same update on tier 2. Never cut by the cap (reserved); the training games restart."""
        from svg_training.opponents.scripted import make_strategy
        g, ex, T = self.gates, self.exploit, self.T
        n, seed = int(g.run["curve_games"]), int(g.run["curve_seed"])
        reads = [(self.tier, "own", self.learner.team())]
        if self.tier == 2:
            reads.append((1, "own", self.learner.team()))
            peer = self.peer_team(self.learner.updates)
            if peer is not None:
                reads.append((2, "t1", peer))
        started = time.perf_counter()
        try:
            for tier, who, team in reads:
                t0 = time.perf_counter()
                opp = make_strategy(self.opp, "strike", self.cfg(tier), n, self.device, seed + ex.STRIKE_SEED_OFFSET)
                c = ex.play_fresh(self.cfg(tier), g.run["size"], n, seed, ex.HeldPlayer(team, self.hold), opp,
                                  self.device, self.ticks_cap, self.stop_final, world=self.view(n) if tier == 2 else None)
                curve.append({"update": self.learner.updates, "game_steps": self.learner.game_steps, "tier": tier,
                              "networks": self.arm if who == "own" else "t1", "k": c["holds"], "n": c["games"],
                              "rate": c["holds"] / c["games"] if c["games"] else None, "unfinished": c["unfinished"],
                              "seconds": time.perf_counter() - t0, "not_one_for_one": c["not_one_for_one"],
                              "nonfinite_actions": c["nonfinite_actions"], "seed": seed, "motion": c["motion"],
                              "tier_ran": T.batch_tier(c), "physics_nonfinite": c["physics_nonfinite"],
                              "upsets": c["upsets"]})
        except self.sweep.SweepStopped:
            return self.stop("interrupted")
        self.state["last_curve_s"] = time.perf_counter() - started
        self.state.setdefault("curve_s_all", []).append(self.state["last_curve_s"])
        write_json(self.run_dir / CURVE, curve)
        controls = self.controls()
        for key, field, word in (("tags_one_for_one_curve", "not_one_for_one", FAIL),
                                 ("no_nonfinite_actions_curve", "nonfinite_actions", NONFINITE),
                                 ("ctl_no_nonfinite_wrench_curve", "physics_nonfinite", FAIL)):
            count = sum(int(p[field]) for p in curve)
            controls[key] = {"status": PASS if count == 0 else word, "phase": "curve", "count": count,
                             "detail": f"{count} games, actions or wrenches wrong over {len(curve)} curve reads"}
        wrong = sum(int(p["tier_ran"] != p["tier"]) for p in curve)
        controls["ctl_batch_tier_curve"] = {"status": PASS if wrong == 0 else FAIL, "phase": "curve", "count": wrong,
                                            "detail": f"{wrong} curve reads ran on another tier than they are read as"}
        code = self.ending(controls, "in a learning-curve read")
        if code is not None:
            return code
        self.save_controls(controls)
        self.refresh()
        say("curve: " + ", ".join(f"tier {p['tier']} {p['networks']} {p['k']}/{p['n']}" for p in curve
                                  if p["update"] == self.learner.updates))
        return None

    # ------------------------------------------------------------------------------------------- 3. final
    def phase_final(self) -> int:
        import numpy as np
        g, ex, T = self.gates, self.exploit, self.T
        self.torch.save(self.learner.modules(), self.run_dir / AGENT_FINAL)
        team = self.learner.team()
        players, cells = None, list(self.cells)
        peer_update = None
        if self.tier == 2:
            t1_res = read_json(self.args.t1_run / RESULTS)
            peer_update = min(self.learner.updates, int(t1_res["trained_updates"]))
            peer = self.peer_team(peer_update)
            if peer is not None:
                players = {T.PEER: peer}
                cells.append((T.PEER, self.opp))
        try:
            pgs = {1: self.batch(1, cells, team, self.stop_final, players)}
            if self.tier == 2:
                pgs[2] = self.batch(2, cells, team, self.stop_final, players)
        except self.sweep.SweepStopped:
            return self.stop("interrupted")
        controls = self.controls()
        for tier, pg in pgs.items():
            np.savez_compressed(self.run_dir / f"eval_final_t{tier}.npz",
                                **{k: v for k, v in pg.items() if isinstance(v, np.ndarray)})
            controls.update(plumbing(ex, pg, self.ref, self.n_eval, "final", f"_t{tier}_final"))
            controls.update(batch_controls(T, pg, tier, "final", f"_t{tier}_final"))
        t44 = {k: v[:self.n_eval] for k, v in self.ref.cell(g.reference["variant"], self.parked, self.opp).items()}
        good, text = ex.replay_ok(self.per_cell(pgs[1], cells)[self.cells[1]], t44, self.device, g.controls,
                                  ticks_cap=self.ticks_cap)
        controls["ctl_reference_replay_final"] = {"status": PASS if good else FAIL, "phase": "final",
                                                  "detail": f"tier 1 {self.parked} v {self.opp} replays T44: {text}"}
        code = self.ending(controls, "in the final batches")
        if code is not None:
            return code
        self.save_controls(controls)
        result = self.results(pgs, cells, peer_update, controls)
        if self.args.no_videos:
            result["videos"] = ["videos not made: --no-videos (tests only)"]
        else:
            from svg_training.viz.replay import RecordingStopped
            try:
                result["videos"] = self.clips()
            except (self.sweep.SweepStopped, RecordingStopped):           # QC D4: SIGINT during the clips -> exit 4
                return self.stop("interrupted")
        result["complete"] = True                    # written last: a crash before here leaves no complete results.json
        write_json(self.run_dir / RESULTS, result)
        write_md(self.run_dir, g, self.arm, controls, result)
        self.state["phase"] = "done"
        self.guard.save(self.learner.updates, self.state)
        say(f"done: arm {self.arm}, trained {result['trained']['k']}/{result['trained']['n']} holds on tier {self.tier}, "
            f"parked {result['parked']['k']}/{result['parked']['n']}; bar cleared {result['bar']['cleared']}; budget "
            f"reached {result['budget_reached']}; {self.run_dir / 'results.md'}")
        return 0

    def results(self, pgs: dict, cells: list, peer_update: int | None, controls: dict) -> dict:
        import numpy as np
        import ste_exploit_l012 as l012
        g, ex, T, sw = self.gates, self.exploit, self.T, self.sweep
        own = self.per_cell(pgs[self.tier], cells)
        k_t, n_t = self.holds(own[cells[0]])
        tier_t = self.counted_tier
        k_p, n_p = self.holds(own[cells[1]])
        tier_p = self.counted_tier
        before = self.state["before"]
        comp = lambda x, tier: sw.hold_composition({**x, "game_ticks": pgs[tier]["game_ticks"]}, self.guards)  # noqa: E731
        batches = {f"tier {tier}": {f"{c[0]} v {c[1]}": ex.counts(v) for c, v in self.per_cell(pg, cells).items()}
                   for tier, pg in pgs.items()}
        log = l012.read_train_log(self.run_dir)
        rates = [x["game_steps_per_s"] for x in log if x.get("game_steps_per_s")]
        out = {
            "what": "STE L0.13 Does tier 2 train at all? One arm; observed in the training simulator",
            "simulator": SIMULATOR[self.tier], "arm": self.arm, "tier": self.tier, "gates_sha256": g.sha256,
            "eval_games": self.n_eval, "opponent": self.opp, "parked_name": self.parked,
            "trained": {**T.rate(k_t, n_t), "composition": comp(own[cells[0]], self.tier),
                        "tier_ran": tier_t, "upsets": int(np.sum(own[cells[0]].get("upset", 0)))},
            "parked": {**T.rate(k_p, n_p), "composition": comp(own[cells[1]], self.tier),
                       "tier_ran": tier_p, "upsets": int(np.sum(own[cells[1]].get("upset", 0)))},
            "upsets": {f"tier {tier}": {f"{c[0]} v {c[1]}": int(np.sum(v.get("upset", 0)))
                                        for c, v in self.per_cell(pg, cells).items()} for tier, pg in pgs.items()},
            "physics_nonfinite": {f"tier {tier}": int(pg["physics_nonfinite"]) for tier, pg in pgs.items()},
            "motion": {f"tier {tier}": pg["motion"] for tier, pg in pgs.items()},
            "untrained": T.rate(*before[self.tier]["untrained"]),
            "bar": T.trains_bar((k_t, n_t), (k_p, n_p)),
            "batches": batches, "peer_update": peer_update,
            "trained_updates": self.learner.updates, "game_steps": self.learner.game_steps,
            "planned_updates": g.planned_updates, "planned_game_steps": g.planned_game_steps,
            "budget_reached": self.learner.updates >= g.planned_updates,
            "train_stop": self.state.get("train_stop"), "train_s": self.state.get("train_s"),
            "final_reserve_s": self.state.get("final_reserve_s"), "controls_batch_s": self.state.get("batch_s"),
            "game_steps_per_s_median": float(np.median(rates)) if rates else None,
            "stale_tick_share_mean": float(np.mean([x["stale_tick_share"] for x in log])) if log else None,
            "filter_share_mean": float(np.mean([x["filter_share"] for x in log])) if log else None,
            "num_games": int(g.trainer["num_games"]), "decision_ticks": self.hold, "train_seed": int(g.run["train_seed"]),
            "device": self.device, "dry_cpu": bool(self.args.dry_cpu), "launches": self.state["launches"],
            "controls_all_pass": all(v["status"] == PASS for v in controls.values()),
            "curve": read_json(self.run_dir / CURVE, []),
            "effective_s": self.guard.effective_s(), "cap_h": self.args.cap_h, "machine": machine(self.device),
            "code": read_json(self.run_dir / "code.json"), "t1_run": None if self.args.t1_run is None else str(self.args.t1_run),
            "game_file": {"file": g.run["game_file"], "sha256": g.run["game_sha256"]},
            "parameter_set": parameter_set(self.cfg(self.tier), self.tier),
        }
        out["projection_for_run_of_record"] = self.projection(rates and float(np.median([x["seconds"] for x in log])))
        if self.tier == 2:
            parked_before = before[2]["parked"]
            info = read_json(self.run_dir / INFO_FILE, {})
            ag = ex.agreement(own[cells[1]], {k: v for k, v in
                                              self.per_cell(np.load(self.run_dir / "eval_before_t2.npz"), self.cells)
                                              [self.cells[1]].items()})
            info["parked_t2_before_v_final"] = {"before": parked_before, "final": [k_p, n_p], **ag,
                                                "note": "INFO: the same starts on the same world, before and after training"}
            write_json(self.run_dir / INFO_FILE, info)
            out["info"] = info
            if T.PEER in [c[0] for c in cells]:
                t2_on_t2 = own[cells[0]]["outcome"] == ex.GUARD_WIN
                peer_on_t1 = self.per_cell(pgs[1], cells)[cells[2]]["outcome"] == ex.GUARD_WIN
                out["paired_t2_on_t2_v_t1_on_t1"] = {"both": int(np.sum(t2_on_t2 & peer_on_t1)),
                                                     "t2_only": int(np.sum(t2_on_t2 & ~peer_on_t1)),
                                                     "t1_only": int(np.sum(~t2_on_t2 & peer_on_t1)),
                                                     "neither": int(np.sum(~t2_on_t2 & ~peer_on_t1))}
        return out

    def projection(self, update_s: float | None) -> dict | None:
        """QC C1: this arm's measured pre-training time, update time U and curve read time C put into the run of
        record's gate file (configs/ste_l013/gates.toml): does that arm reach its budget, with what margin, and the
        break-even rate. Printed at the end of every arm (the smoke's numbers are the run's projection)."""
        if not update_s:
            return None
        import numpy as np
        reads = self.state.get("curve_s_all") or [0.0]
        p = self.T.projection(self.T.load_gates(self.T.GATES_FILE), self.arm, float(self.state.get("pre_s", 0.0)),
                              float(update_s), float(np.median(reads)), float(self.state.get("batch_s", 0.0)))
        say(f"projection for the run of record, arm {self.arm}: pre {p['pre_s']:.0f} s + {p['updates'] - 1}.5 x U "
            f"{p['update_s']:.1f} s + {p['reads'] - 1}.5 x C {p['curve_s']:.1f} s = {p['need_s']:.0f} s <= cap - reserve "
            f"{p['available_s']:.0f} s: margin {p['margin_s']:+.0f} s; break-even "
            f"{p['break_even_game_steps_per_s']:,.0f} game-steps/s")
        return p

    def clips(self) -> list[str]:
        """STANDARDS section 8: the final networks v the opponent, the arm's own tier, 2-D with the height panel. t1 on
        the CPU; t2 on a view of the Isaac world (frames copied to the host). CLIP-T2 (24 Nov 2026): both arms play the
        clip starts drawn once on the CPU from the clip seed and the tier-1 game file (``viz.replay.cpu_starts``; the t1
        arm's own draw), not t2's own CUDA draw: same starts, same game file; the tag, strategy and estimator noise
        streams are each device's own."""
        import ste_exploit_l012 as l012
        from svg_training.opponents.scripted import make_strategy
        from svg_training.ste import exploit_train
        from svg_training.viz.replay import cpu_starts, record_games, render_replay
        g, v = self.gates, self.gates.videos
        n, seed = int(v["games"]), int(g.run["clip_seed"])
        dev = "cpu" if self.tier == 1 else self.device
        team = exploit_train.team_from_modules("guard", self.learner.modules(), list(g.trainer["hidden"]), dev)
        team.name = f"Guard team trained on tier {self.tier} (arm {self.arm})"
        opp = make_strategy(self.opp, "strike", self.cfg(self.tier), n, dev, seed + self.exploit.STRIKE_SEED_OFFSET)
        starts = cpu_starts(self.cfg1, n, self.guards, self.strikes, seed, band=0)
        recs = record_games(self.cfg(self.tier), self.guards, self.strikes, self.exploit.HeldPlayer(team, self.hold), opp,
                            num_games=n, seed=seed, band=0, max_steps=int(v["max_ticks"]), device=dev,
                            world=self.view(n) if self.tier == 2 else None, should_stop=self.stop_final, starts=starts)
        out = []
        for rec in l012.pick_videos(recs, int(v["keep"])):
            kind = "reach" if rec.outcome == self.exploit.STRIKE_WIN else "hold"
            path = render_replay(rec, self.run_dir / "videos" / f"l013_{self.arm}_tier{self.tier}_game{rec.game_index}_{kind}.gif",
                                 speed=int(v["speed"]), fps=int(v["fps"]), dpi=int(v["dpi"]),
                                 playback_label=f"{int(v['speed']) * int(v['fps']) * 0.05:g}x real time")
            out.append(f"videos/{path.name}: tier {self.tier}, game {rec.game_index}, {kind} at {rec.end_time_s:.1f} s "
                       f"({path.stat().st_size / 1e6:.2f} MB)")
            say(out[-1])
        return out or [f"no clip game finished within {v['max_ticks']} ticks: no video"]


def tier_ran(cell_pg: dict) -> int | None:
    """The one tier every game of a cell ran on (the batch's "tier" array), None if they differ (QC T2)."""
    import numpy as np
    tiers = np.unique(np.asarray(cell_pg["tier"]))
    return int(tiers[0]) if len(tiers) == 1 else None


def batch_controls(T, pg: dict, tier: int, phase: str, suffix: str) -> dict:
    """QC F1, T2 (gated): the batch ran on the tier it is read as (its drone model), and the physics drone met no
    non-finite wrench or setpoint in it (``physics_nonfinite``; 0 on tier 1). The upsets are INFO (results.json)."""
    ran = T.batch_tier(pg)
    nf = int(pg["physics_nonfinite"])
    return {f"ctl_batch_tier{suffix}": {"status": PASS if ran == tier else FAIL, "phase": phase,
                                        "detail": f"batch read as tier {tier} ran {pg['motion']!r} (tier {ran})"},
            f"ctl_no_nonfinite_wrench{suffix}": {"status": PASS if nf == 0 else FAIL, "phase": phase,
                                                 "detail": f"{nf} non-finite wrenches or setpoints in the drone model"}}


def plumbing(ex, pg: dict, ref, n: int, phase: str, suffix: str) -> dict:
    """Paired starts, one for one, no non-finite action, on one evaluation batch (gate [controls])."""
    import numpy as np
    want = ex.starts_sha(ref.starts_m[:n])
    shas = set(pg["start_sha256"])
    bad = int(np.sum((pg["guards_removed"] != pg["tags"]) | (pg["guards_tagged"] != pg["tags"])))
    nf = int(pg["nonfinite_actions"].sum())
    return {f"ctl_paired_starts{suffix}": {"status": PASS if shas == {want} else FAIL, "phase": phase,
                                           "detail": f"{len(shas)} start set(s), reference {want[:12]}"},
            f"tags_one_for_one{suffix}": {"status": PASS if bad == 0 else FAIL, "phase": phase,
                                          "detail": f"{bad} games not one for one of {len(pg['tags'])}"},
            f"no_nonfinite_actions{suffix}": {"status": PASS if nf == 0 else NONFINITE, "phase": phase,
                                              "detail": f"{nf} non-finite actions"}}


def machine(device: str) -> dict:
    import torch
    dev = torch.cuda.get_device_name(0) if str(device).startswith("cuda") and torch.cuda.is_available() else "cpu"
    return {"host": platform.node(), "gpu": dev, "torch": torch.__version__, "python": platform.python_version()}


def parameter_set(cfg, tier: int) -> dict:
    """The drone model of a tier with its file and sha256 (tier 1: the fitted PX4 response; tier 2: the physics file)."""
    from svg_training.ste import tier2_train as T
    if tier == 1:
        path = T.ROOT / cfg.starling.params
        return {"file": str(cfg.starling.params), "sha256": T.sha256_file(path),
                "filter": f"every pair, {cfg.starling.filter_iterations} sweeps, check every {cfg.starling.filter_check_every}"}
    from svg_training.core.starling_layer import resolve_params
    path = Path(resolve_params(cfg.starling.physics_params))
    return {"file": str(cfg.starling.physics_params), "sha256": T.sha256_file(path) if path.is_file() else None,
            "sim_only_gains": cfg.starling.physics_sim_only_gains,
            "filter": f"every pair, {cfg.starling.filter_iterations} sweeps, check every {cfg.starling.filter_check_every}"}


def _pct(d: dict | None) -> str:
    if not d or not d.get("n"):
        return "n/a"
    return f"{d['k']}/{d['n']} = {d['k'] / d['n']:.3f} ({d['ci'][0]:.3f}-{d['ci'][1]:.3f})"


def write_md(run_dir: Path, gates, arm: str, controls: dict, result: dict | None) -> None:
    from svg_training.ste import atomic, tier2_train as T
    tier = T.TIERS[arm]
    lines = [f"Simulator: {SIMULATOR[tier]}. Observed in the training simulator; nothing here is a flight result.", "",
             f"# L0.13 Does tier 2 train at all? Arm {arm} (tier {tier})", "",
             f"- Gate file sha256 `{gates.sha256}`; {gates.run['eval_games']} evaluation games per cell on T44's starts; "
             f"{gates.trainer['num_games']:,} games at once; {gates.planned_updates} updates = "
             f"{gates.planned_game_steps:,} game-steps planned.", "",
             "## Controls (read these first)", "", "| Control | Phase | Status | Detail |", "|---|---|---|---|"]
    lines += [f"| {k} | {v.get('phase', '')} | **{v['status']}** | {v['detail']} |" for k, v in controls.items()]
    if result is None:
        lines += ["", "**No result: a control did not PASS.** A diagnostic of the run folder, not a result."]
    else:
        lines += ["", f"## Result: hold rate against {result['opponent']} on tier {tier} (Wilson 95 %)", "",
                  "| Guard team | Holds | Length median / p90 (s) |", "|---|---|---|",
                  f"| trained (arm {arm}, update {result['trained_updates']}) | {_pct(result['trained'])} | "
                  f"{result['trained']['composition']['length_median_s']} / {result['trained']['composition']['length_p90_s']} |",
                  f"| parked ({result['parked_name']}, same batch) | {_pct(result['parked'])} | "
                  f"{result['parked']['composition']['length_median_s']} / {result['parked']['composition']['length_p90_s']} |",
                  f"| untrained (before training) | {_pct(result['untrained'])} | |", "",
                  f"Bar (trained lower bound above parked upper bound): **{result['bar']['cleared']}**. Budget reached: "
                  f"**{result['budget_reached']}** ({result['train_stop']}). Median "
                  f"{result['game_steps_per_s_median'] or 0:,.0f} game-steps/s at {result['num_games']:,} games, 6 drones "
                  f"per game, {result['machine']['gpu']}; effective {result['effective_s']:.0f} s of {result['cap_h']} h.", "",
                  "## Every cell of the final batches", "", "| Batch | Cell | Holds | Reaches | Games |", "|---|---|---|---|---|"]
        for b, cells in result["batches"].items():
            lines += [f"| {b} | {c} | {v['holds']} | {v['reaches']} | {v['games']} |" for c, v in cells.items()]
        lines += ["", "## Learning curve (curve starts, never the scoring starts)", "",
                  "| Update | Game-steps | Tier | Networks | Holds |", "|---|---|---|---|---|"]
        lines += [f"| {p['update']} | {p['game_steps']:,} | {p['tier']} | {p['networks']} | {p['k']}/{p['n']} |"
                  for p in result["curve"]]
        lines += ["", "## Videos", ""] + [f"- {v}" for v in result.get("videos", [])]
    atomic.write_text(run_dir / "results.md", "\n".join(lines) + "\n")


# ================================================================================================ the verdict
def verdict_main(argv: list[str]) -> int:
    """The gate's verdict over the two arms (CPU): verdict.json, verdict.md and learning_curves.png in --out."""
    from svg_training.ste import atomic, tier2_train as T
    ap = argparse.ArgumentParser(prog="ste_tier2_l013.py verdict")
    ap.add_argument("--t1-run", type=Path, required=True)
    ap.add_argument("--t2-run", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--smoke", action="store_true", help="arms run under another gate file than configs/ste_l013/"
                    "gates.toml (the smoke, tests): the verdict is labelled SMOKE, never PASS / FAIL / TOO_SLOW")
    a = ap.parse_args(argv)
    res = {}
    for arm, d in (("t1", a.t1_run), ("t2", a.t2_run)):
        r = read_json(d / RESULTS)
        if not r or r.get("complete") is not True or r.get("arm") != arm:
            return refuse(f"{d} has no complete arm {arm} {RESULTS} (not finished, stopped or a control failed): an "
                          f"ABORTED record, not a verdict (make_ste_l013_record.py --aborted)")
        bad = [k for k, v in read_json(d / CONTROLS_FILE, {}).items() if v.get("status") != PASS]
        if bad:
            return refuse(f"{d}: control(s) {bad} not PASS: an ABORTED record, not a verdict")
        code = (d / "exit_code").read_text().strip() if (d / "exit_code").is_file() else None
        if code is not None and code != "0":
            return refuse(f"{d}: the job's recorded exit is {code}, not 0")
        res[arm] = {**r, "dir": str(d.resolve())}
    if res["t1"]["gates_sha256"] != res["t2"]["gates_sha256"]:
        return refuse("the two arms ran under different gate files")
    if Path(res["t2"]["t1_run"]).resolve() != a.t1_run.resolve():
        return refuse(f"arm t2 scored the t1 arm {res['t2']['t1_run']}, not {a.t1_run}")
    if res["t1"]["dry_cpu"] != res["t2"]["dry_cpu"]:
        return refuse("a dry CPU arm and a run of record never pair")
    gates = T.load_gates(Path(res["t2"]["dir"]) / GATES_COPY)
    of_record = T.sha256_file(T.GATES_FILE)
    if gates.sha256 != of_record and not a.smoke:                       # QC D2
        return refuse(f"the arms ran under gate sha256 {gates.sha256}, not configs/ste_l013/gates.toml's {of_record}: "
                      "a smoke or test verdict needs --smoke (labelled SMOKE)")
    t1, t2 = res["t1"], res["t2"]
    for arm, r in (("t1", t1), ("t2", t2)):                             # QC T2: each arm's numbers from its own tier
        ran = {who: r[who].get("tier_ran") for who in ("trained", "parked")}
        if any(x != T.TIERS[arm] for x in ran.values()):
            return refuse(f"arm {arm}'s trained / parked numbers ran on tier {ran}, not tier {T.TIERS[arm]}")
    v = T.tier2_verdict((t2["trained"]["k"], t2["trained"]["n"]), (t2["parked"]["k"], t2["parked"]["n"]),
                        t2["budget_reached"], t2["game_steps"], t1["bar"]["cleared"],
                        t1_budget_reached=t1["budget_reached"])
    b1, b2 = t2["batches"]["tier 1"], t2["batches"]["tier 2"]
    peer = f"{T.PEER} v {t2['opponent']}"
    own = f"{T.EXPLOITER} v {t2['opponent']}"
    matrix = {"t2 networks": {"tier 1": b1[own], "tier 2": b2[own]},
              "t1 networks": {"tier 1": b1.get(peer), "tier 2": b2.get(peer)}, "update": t2["peer_update"]}
    out = {"task": "L0.13", "what": "Does tier 2 train at all? Observed in the training simulator",
           "gates_sha256": gates.sha256, "verdict": "SMOKE" if a.smoke else v["verdict"], "detail": v,
           "smoke": bool(a.smoke), "smoke_reading": v["verdict"] if a.smoke else None,
           "t1": {k: t1[k] for k in ("trained", "parked", "untrained", "bar", "budget_reached", "game_steps",
                                     "trained_updates", "game_steps_per_s_median", "effective_s", "train_stop", "dir",
                                     "machine", "videos", "curve", "dry_cpu")},
           "t2": {k: t2[k] for k in ("trained", "parked", "untrained", "bar", "budget_reached", "game_steps",
                                     "trained_updates", "game_steps_per_s_median", "effective_s", "train_stop", "dir",
                                     "machine", "videos", "curve", "info", "paired_t2_on_t2_v_t1_on_t1", "peer_update",
                                     "dry_cpu")},
           "same_game_steps": t1["game_steps"] == t2["game_steps"],
           "own_tier": {"t1 on tier 1": t1["trained"], "t2 on tier 2": t2["trained"],
                        "difference": t2["trained"]["rate"] - t1["trained"]["rate"]},
           "matrix_same_update": matrix,
           "l012_scale": {"holds": gates.l012["base_guard_holds"], "games": gates.l012["base_guard_games"],
                          "game_steps": gates.l012["base_guard_game_steps"], "record": gates.l012["record"]},
           "controls_pass": True}
    a.out.mkdir(parents=True, exist_ok=True)
    out["figure"] = curve_figure(t1["curve"], t2["curve"], t2["parked"], t1["parked"], a.out / "learning_curves.png")
    write_json(a.out / "verdict.json", out)
    atomic.write_text(a.out / "verdict.md", verdict_md(out))
    say(f"verdict {v['verdict']}: t2 {_pct(t2['trained'])} v parked {_pct(t2['parked'])} on tier 2; {a.out / 'verdict.md'}")
    return 0


def curve_figure(c1: list, c2: list, parked2: dict, parked1: dict, path: Path) -> str:
    """Hold rate against game-steps: each arm's networks on its own tier, t2's networks on tier 1 and t1's networks on
    tier 2 (dashed); the parked Guard's final rate on each tier as a band (its Wilson interval)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=110)
    series = [("t1 networks on tier 1", [p for p in c1 if p["tier"] == 1], "#2f6db3", "-"),
              ("t2 networks on tier 2", [p for p in c2 if p["tier"] == 2 and p["networks"] == "t2"], "#c2492f", "-"),
              ("t2 networks on tier 1", [p for p in c2 if p["tier"] == 1], "#c2492f", ":"),
              ("t1 networks on tier 2", [p for p in c2 if p["tier"] == 2 and p["networks"] == "t1"], "#2f6db3", ":")]
    for name, pts, colour, style in series:
        if pts:
            ax.plot([p["game_steps"] / 1e6 for p in pts], [p["rate"] for p in pts], style, marker="o", ms=3,
                    color=colour, label=name)
    for parked, colour, name, hatch in ((parked1, "#2f6db3", "parked Guard, tier 1", "//"),
                                        (parked2, "#c2492f", "parked Guard, tier 2", "\\\\")):
        ax.axhspan(parked["ci"][0], parked["ci"][1], facecolor=matplotlib.colors.to_rgba(colour, 0.10),
                   edgecolor=colour, linewidth=1.2, hatch=hatch, label=name)   # outlined: two overlapping bands stay visible
    ax.set_xlabel("game-steps trained (millions)")
    ax.set_ylabel("hold rate (curve starts)")
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, loc="lower right")
    ax.set_title("L0.13: Guard team v strike_straight, tier 1 and tier 2 (training simulator)", fontsize=9)
    first = (c1 or c2)[0]
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.text(0.01, 0.01, f"Curves on {first['n']:,} curve starts (seed {first['seed']}); band = the parked Guard's "
             f"{parked1['n']:,}-start interval (Wilson 95 %), read once on the final batch.", fontsize=7, color="#444444")
    fig.savefig(path)
    plt.close(fig)
    return path.name


def verdict_md(out: dict) -> str:
    d, t1, t2 = out["detail"], out["t1"], out["t2"]
    m = out["matrix_same_update"]
    dry = " **DRY CPU RUN (tests): not of record.**" if t2["dry_cpu"] else ""
    if out.get("smoke"):                                                # QC D2: a smoke is never a result
        dry += f" SMOKE (another gate file than gates.toml): the gate's rule would read {out['smoke_reading']}; not a result."
    lines = ["Simulator: training simulator, tier 1 (fitted Starling response) and tier 2 (Isaac Lab rigid-body Starling); "
             "study tag on (P1, PROPOSED). Observed in the training simulator; nothing here is a flight result.", "",
             "# L0.13 Does tier 2 train at all? Verdict", "", f"**{out['verdict']}**{dry}", "",
             f"- Gate file sha256 `{out['gates_sha256']}`.",
             f"- Tier 2 trained Guard {_pct(t2['trained'])} holds v parked Guard {_pct(t2['parked'])} (same batch, tier 2): "
             f"bar cleared **{d['bar']['cleared']}**; budget reached **{d['budget_reached']}** ({d['game_steps']:,} "
             f"game-steps)." + (f" Reading: {d['reading']}." if d["reading"] else ""),
             f"- Tier 1 control {_pct(t1['trained'])} v parked {_pct(t1['parked'])} on tier 1: bar cleared "
             f"{t1['bar']['cleared']}; {t1['game_steps']:,} game-steps (same as t2: {out['same_game_steps']}).",
             f"- Scale: L0.12's base Guard held {out['l012_scale']['holds']}/{out['l012_scale']['games']} on tier 1 at "
             f"{out['l012_scale']['game_steps']:,} game-steps ({out['l012_scale']['record']}).", "",
             f"## Networks x tiers at update {m['update']} (T44's starts, INFO)", "",
             "| Networks | Tier 1 holds | Tier 2 holds |", "|---|---|---|"]
    for who in ("t2 networks", "t1 networks"):
        row = m[who]
        cell = lambda c: "n/a" if not c else f"{c['holds']}/{c['games']}"  # noqa: E731
        lines.append(f"| {who} | {cell(row['tier 1'])} | {cell(row['tier 2'])} |")
    if t2.get("paired_t2_on_t2_v_t1_on_t1"):
        p = t2["paired_t2_on_t2_v_t1_on_t1"]
        lines += ["", f"Paired by start (t2 networks on tier 2 v t1 networks on tier 1, same update): held in both "
                      f"{p['both']}, t2 only {p['t2_only']}, t1 only {p['t1_only']}, neither {p['neither']}."]
    lines += ["", f"Rates: t1 median {t1['game_steps_per_s_median'] or 0:,.0f} game-steps/s, t2 "
                  f"{t2['game_steps_per_s_median'] or 0:,.0f}; effective s t1 {t1['effective_s']:.0f}, t2 "
                  f"{t2['effective_s']:.0f}.", "", f"![learning curves]({out['figure']})", "", "Clips:"]
    lines += [f"- t1: {x}" for x in t1["videos"]] + [f"- t2: {x}" for x in t2["videos"]]
    return "\n".join(lines) + "\n"


# ================================================================================================ arm t2: Isaac first
def _isaac_cli() -> int:
    """Arm t2: Isaac Sim starts headless before torch is imported; the process leaves through os._exit (Kit's shutdown
    swallows exit codes). Ctrl-C during the start exits 4."""
    code = 1
    try:
        from _isaac_app import start_headless
        args, _app = start_headless(parser(isaac=True))
        args.headless = True
        code = run(args)
    except KeyboardInterrupt:
        code = 4
    except SystemExit as ex:                      # start_headless refuses with SystemExit(2)
        code = ex.code if isinstance(ex.code, int) else 2
    except BaseException:  # noqa: BLE001  (any failure: printed; the waiter reads FAILED)
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)          # never simulation_app.close() (it swallows exit codes)
    return code


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv[:1] != ["verdict"] and "t2" in argv and "--dry-cpu" not in argv:
        problem = pre_isaac_problem(argv)
        if problem:
            print(f"refused: {problem[1]}" if problem[0] == 2 else problem[1], file=sys.stderr)
            sys.exit(problem[0])
        _isaac_cli()
    sys.exit(main())
