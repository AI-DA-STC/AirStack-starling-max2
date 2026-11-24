#!/usr/bin/env python
"""STE L3-L6 pipeline check, task L3.1: the Isaac smoke of the tier-2 skills fixed-choice replay (spec
ste_learning/drafts/L3_L6_PIPELINE_SPEC.md section 4; slice 3 design §3 step 3(b)). Scoring only, a little training
for the reload check; a pipeline check, not for flight.

    # after nvidia-smi and scripts/isaac_preflight.sh --approved-headless (exit 0), alone on the GPU, at the lead's go:
    scripts/ste_job.py launch --task L3.1 --name l3_isaac_smoke --run-dir runs/<d>_ste_l3_isaac_smoke --min-s 60 \\
        --gpu-h 0.3 --settings configs/ste_learning.toml -- <python> scripts/ste_l3_isaac_smoke.py \\
        --gates configs/ste_l3/skills_gates.toml --run-dir runs/<d>_ste_l3_isaac_smoke --cap-h 0.3 --headless
    # --games / --max-ticks make a smaller smoke; --dry-cpu (tests only, never of record): the PyTorch reference world

The six checks (QC's list), each a control; a FAIL ends the smoke (exit 6, terminal in its folder):
1. ``ctl_replay_<side>``: on tier 2, each team strategy and each uniform drone skill played as a fixed two-level team
   equals that script on tier 2, and three mixed "free" combinations equal the composite player, against the run's
   opponent, on T44's first starts (``exploit.replay_ok``: game for game on the CPU, the gate's CUDA tolerances on
   CUDA).
2. ``ctl_device_placement``: the dispatch maps, the networks, the observations and a decision's outputs on the device;
   on CUDA, no host sync inside the dispatch (``SyncCount``: torch's sync debug mode, a prototype); not checked on the
   CPU. HeldPlayer's choice log (a boolean-mask index) and the game step are not covered.
3. ``ctl_reload_across_devices``: a two-level learner (one update on tier 2) saved on the device reloads on the CPU
   (``skill_team_from_modules``) with logits within 1e-5 and the same greedy choices on recorded tier-2 observations.
4. ``ctl_clips``: exactly two clips of a fixed two-level team on tier 2 (the CPU clip starts, as CLIP-T2).
5. ``ctl_nonfinite_stale``: no non-finite action and no non-finite physics value in any batch or the update; the
   decision loop's stale-tick share is recorded (INFO).
6. ``throughput`` (INFO): game-steps per second of a two-level team against one script, same size (spec B1).

Upsets are recorded per side (INFO). The CUDA replay tolerances are exercised only by the Isaac run. ``of_record`` in
results.json: true only on Isaac at the gate file's games and tick cap; on Isaac a smaller smoke needs --small-test.

Exit codes: 0 done; 2 refused; 3 cap; 4 stopped; 5 a non-finite value; 6 a control failed. ``results.json`` last."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

from ste_tier2_score_l18 import isaac_world_factory, torch_world_factory  # noqa: E402

HOUR_S = 3600.0
CONTROLS_FILE, RESULTS, PINNED = "controls.json", "results.json", "gates.sha256"
PASS, FAIL, NONFINITE, INFO = "PASS", "FAIL", "NONFINITE", "INFO"
STATUS = "pipeline check, not for flight"
HOLD = 12
MIXED = ((0, 1, 2), (2, 2, 0), (1, 0, 1))     # "free" combinations of drone skills per slot (indices into drone_skills)
TRAIN_GAMES = 64                               # the reload check's tiny learner (one update on tier 2)
RELOAD_TOL = 1e-5
CLIP_GAMES = 2


def say(text: str) -> None:
    print(f"[l3 smoke] {text}", flush=True)


def refuse(text: str) -> int:
    print(f"refused: {text}", file=sys.stderr, flush=True)
    return 2


def parser(isaac: bool = False) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--gates", type=Path, required=True)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--cap-h", type=float, required=True)
    ap.add_argument("--games", type=int)
    ap.add_argument("--max-ticks", type=int)
    ap.add_argument("--dry-cpu", action="store_true", help="tests only: CPU, the PyTorch reference world")
    ap.add_argument("--small-test", action="store_true",
                    help="tests only on Isaac: allow --games / --max-ticks below the gate file's (never of record)")
    if not isaac:
        ap.add_argument("--headless", action="store_true", help="required without --dry-cpu (Isaac Lab)")
    return ap


def of_record(gates, dry_cpu: bool, games: int, ticks: int) -> bool:
    """A smoke of record: on Isaac (not --dry-cpu) with the gate file's evaluation games and tick cap."""
    return (not dry_cpu) and games == int(gates.run["eval_games"]) and ticks == int(gates.run["ticks_cap"])


class SyncCount:
    """A two-level team whose dispatch calls (``choose``, ``command``, ``act``) run under
    ``torch.cuda.set_sync_debug_mode("warn")`` on CUDA, counting the host syncs they cause (check 2: no host read
    inside a tick, for the dispatch; HeldPlayer's choice log and the game step are outside it). Not checked on the
    CPU (no host/device boundary); the PyTorch sync debug mode is a prototype that does not see every sync."""

    def __init__(self, inner, device: str):
        self.inner, self.checked, self.syncs = inner, str(device).startswith("cuda"), 0

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def _counted(self, fn, *args):
        if not self.checked:
            return fn(*args)
        import warnings

        import torch
        prev = torch.cuda.get_sync_debug_mode()
        torch.cuda.set_sync_debug_mode("warn")
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                out = fn(*args)
        finally:
            torch.cuda.set_sync_debug_mode(prev)
        self.syncs += sum(1 for w in caught if "synchroniz" in str(w.message))
        return out

    def choose(self, obs):
        return self._counted(self.inner.choose, obs)

    def command(self, obs, held):
        return self._counted(self.inner.command, obs, held)

    def act(self, obs):
        return self._counted(self.inner.act, obs)


def pre_isaac_problem(argv: list[str]) -> tuple[int, str] | None:
    """Before Isaac Sim starts (standard library only)."""
    if "--headless" not in argv:
        return 2, "the smoke starts Isaac Lab: --headless (after scripts/isaac_preflight.sh --approved-headless)"
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--run-dir", type=Path)
    known, _ = pre.parse_known_args(argv)
    path = known.run_dir / CONTROLS_FILE if known.run_dir is not None else None
    if path is not None and path.is_file():
        statuses = {v.get("status") for v in json.loads(path.read_text()).values()}
        if NONFINITE in statuses:
            return 5, f"a non-finite value was recorded in {path}: no retry"
        if FAIL in statuses:
            return 6, f"a control failed in {path}: terminal, a new run needs a new run folder"
    return None


def main(argv: list[str] | None = None, world_factory=None) -> int:
    return run(parser().parse_args(list(sys.argv[1:] if argv is None else argv)), world_factory)


def run(a: argparse.Namespace, world_factory=None) -> int:
    from svg_training.ste import exploit
    import ste_l3_held_arm as held
    a.run_dir = a.run_dir.resolve()
    try:
        gates = exploit.load_gates(a.gates)
    except (OSError, ValueError) as err:
        return refuse(f"gate file {a.gates}: {err}")
    if not (gates.learner.skills and gates.learner.choice == exploit.skills.TWO_LEVEL):
        return refuse("the smoke replays the two-level skills route: a gate file with [learner] choice = \"two_level\"")
    if not (math.isfinite(a.cap_h) and a.cap_h > 0):
        return refuse(f"--cap-h must be a finite number of hours above 0, got {a.cap_h!r}")
    if not a.dry_cpu and not getattr(a, "headless", True):
        return refuse("the smoke starts Isaac Lab: --headless")
    sizes = (("--games", a.games, gates.run["eval_games"]), ("--max-ticks", a.max_ticks, gates.run["ticks_cap"]))
    small = [f for f, v, full in sizes if v is not None and v < int(full)]
    if small and not a.dry_cpu and not a.small_test:
        return refuse(f"{', '.join(small)} below the gate file's on Isaac: a smoke of record plays the full size; a "
                      f"smaller one needs --small-test (never of record)")
    if not a.dry_cpu and (ROOT / "runs").resolve() not in a.run_dir.parents:
        return refuse(f"{a.run_dir} is not under {ROOT / 'runs'}")
    problem = held.input_problems(gates)
    if problem:
        return refuse(problem)
    n_full, ticks_full = int(gates.run["eval_games"]), int(gates.run["ticks_cap"])
    for flag, value, full in (("--games", a.games, n_full), ("--max-ticks", a.max_ticks, ticks_full)):
        if value is not None and not 0 < value <= full:
            return refuse(f"{flag} {value}: between 1 and the gate file's {full}")
    code = pre_isaac_problem(["--headless", "--run-dir", str(a.run_dir)])
    if code:
        print(code[1], file=sys.stderr, flush=True)
        return code[0]
    res = a.run_dir / RESULTS
    if res.is_file() and json.loads(res.read_text()).get("complete") is True:
        say(f"this run folder is done ({res}); nothing to do")
        return 0
    pinned = a.run_dir / PINNED
    if pinned.is_file() and pinned.read_text().strip() != gates.sha256:
        return refuse(f"the gate file changed since the first launch in {a.run_dir}: a new run folder")

    import torch

    from svg_training.ste.run_contract import RunBusyError, RunGuard
    device = "cpu" if a.dry_cpu else str(gates.run["device"])
    if device.startswith("cuda") and not torch.cuda.is_available():
        return refuse("the gate file plays on cuda and PyTorch sees no GPU")
    job = a.run_dir / "job.json"
    if job.is_file() and abs(float(json.loads(job.read_text()).get("gpu_h", 0)) - a.cap_h) > 1e-9:
        return refuse("the launcher asked for other hours than --cap-h: keep the two equal")
    a.run_dir.mkdir(parents=True, exist_ok=True)
    pinned.write_text(gates.sha256 + "\n")
    factory = world_factory or (torch_world_factory if a.dry_cpu else isaac_world_factory)
    try:
        with RunGuard(a.run_dir, cap_s=a.cap_h * HOUR_S) as guard:
            return Smoke(gates, a, device, factory, guard).run()
    except RunBusyError as err:
        return refuse(str(err))


class Smoke:
    def __init__(self, gates, a, device: str, factory, guard):
        from svg_training.core.physics_layer import load_game_physics_params
        from svg_training.ste import exploit, tier2_train as T
        self.gates, self.a, self.device, self.guard, self.ex, self.T = gates, a, device, guard, exploit, T
        self.n = int(a.games or gates.run["eval_games"])
        self.ticks = int(a.max_ticks or gates.run["ticks_cap"])
        self.cfg1 = exploit.variant_cfg(gates, "base")
        self.cfg2 = self.cfg1.replace(**{T.TIER2_SETTING: T.PHYSICS_BACKEND})
        self.params = load_game_physics_params(self.cfg2)
        self.ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
        self.factory = factory
        self.world = None
        self.controls: dict = {}

    # -------------------------------------------------------------------------------- helpers
    def view(self, k: int):
        return self.T.view(self.world, k, self.params)

    def stop_check(self) -> bool:
        return self.guard.stop_requested or self.guard.cap_reached()

    def batch(self, cells: list, players: dict, hold: int) -> dict:
        n = len(cells) * self.n
        return self.ex.play_cells(self.cfg2, "3v3", self.ref, cells, self.n, self.device, self.ref.meta["seed"],
                                  self.ticks, hold_ticks=hold, players=players, world=self.view(n),
                                  should_stop=self.stop_check)

    def save_controls(self) -> None:
        from svg_training.ste import atomic
        atomic.write_text(self.a.run_dir / CONTROLS_FILE, json.dumps(self.controls, indent=1, sort_keys=True) + "\n")

    def fail(self, word: str = FAIL) -> int:
        self.save_controls()
        bad = [k for k, v in self.controls.items() if v["status"] not in (PASS, INFO)]
        say(f"CONTROL NOT PASS: {bad}; nothing published")
        return 5 if word == NONFINITE else 6

    def team(self, side: str, heads: list, d):
        import torch

        class HeadLogits(torch.nn.Module):
            def __init__(self, t, k, widths):
                super().__init__()
                self.t, self.k, self.widths = t, k, widths

            def forward(self, obs):
                out = obs.new_zeros(obs.shape[0], sum(self.widths))
                out[:, self.t] = 1.0
                out[:, self.widths[0] + self.k] = 1.0
                return out
        return self.ex.SkillTeam(side, [HeadLogits(t, k, d.widths) for t, k in heads],
                                 [lambda o, train=False: o] * len(heads), d)

    # -------------------------------------------------------------------------------- the smoke
    def run(self) -> int:
        from svg_training.ste import skills
        g = self.gates
        largest = max(2 + len(g.learner.drone_skills[s]) + len(MIXED) for s in ("guard", "strike")) * self.n
        self.world = self.factory(max(largest, TRAIN_GAMES), 6, self.params, self.device)
        say(f"world: {getattr(self.world, 'label', type(self.world).__name__)}, {max(largest, TRAIN_GAMES)} games, "
            f"device {self.device}")
        replay_rows, nonfinite, throughput, upsets, syncs, checked = [], 0, {}, {}, 0, False
        for side in ("guard", "strike"):
            other = "strike" if side == "guard" else "guard"
            opp = self.ex.opponent_of(g, "base", side)
            d = skills.two_level_dispatch(g.learner, g.players, side, self.cfg2, self.n, self.device, 0)
            ts, ds = list(g.learner.team_strategies[side]), list(g.learner.drone_skills[side])
            fixed = [(nm, [(t + 1, 0)] * 3, "team strategy") for t, nm in enumerate(ts)]
            fixed += [(nm, [(skills.FREE, k)] * 3, "uniform drone skill") for k, nm in enumerate(ds)]
            mixed = [(f"mix{c}", [(skills.FREE, k) for k in c], "mixed") for c in MIXED]
            mine = {f"tl:{nm}": SyncCount(self.team(side, heads, d), self.device) for nm, heads, _ in fixed + mixed}
            cell = (lambda me: (opp, me)) if side == "strike" else (lambda me: (me, opp))
            started = time.perf_counter()
            pg = self.batch([cell(k) for k in mine], mine, HOLD)
            took = time.perf_counter() - started
            want = self.batch([cell(nm) for nm, _, _ in fixed], {}, 1)
            comp = {f"comp{c}": _Composite(side, [ds[k] for k in c], self.cfg2, self.n, self.device) for c in MIXED}
            got_comp = self.batch([cell(k) for k in comp], comp, 1)
            if side == "guard":
                t0 = time.perf_counter()
                self.batch([cell(ds[0])] * len(mine), {}, 1)
                one = time.perf_counter() - t0
                steps = len(mine) * self.n * self.ticks
                throughput = {"two_level_game_steps_per_s": steps / took, "one_script_game_steps_per_s": steps / one,
                              "ratio": one / took, "games": len(mine) * self.n, "note": "upper bound on steps "
                              "(ticks_cap x games); the ratio is what the spec's B1 reads"}
            ok, details = True, []
            for k, (nm, _, kind) in enumerate(fixed + mixed):
                a_ = self.ex.slice_cell(pg, k, self.n)
                b_ = (self.ex.slice_cell(want, k, self.n) if kind != "mixed" else
                      self.ex.slice_cell(got_comp, k - len(fixed), self.n))
                good, text = self.ex.replay_ok(a_, b_, self.device, g.controls)
                ok &= good
                details.append(f"{nm}: {text}")
                replay_rows.append({"side": side, "cell": nm, "kind": kind, "ok": bool(good), "detail": text})
            self.controls[f"ctl_replay_{side}"] = {"status": PASS if ok else FAIL,
                                                   "detail": f"v {opp}, tier 2: " + "; ".join(details)}
            nonfinite += sum(int(x["nonfinite_actions"].sum()) + int(x["physics_nonfinite"])
                             for x in (pg, want, got_comp))
            upsets[side] = {k: int(x["upset"].sum()) if "upset" in x else 0
                            for k, x in (("two_level", pg), ("scripts", want), ("composite", got_comp))}
            syncs += sum(w.syncs for w in mine.values())
            checked = all(w.checked for w in mine.values())
            if not ok:
                return self.fail()
        checks, extra = self.device_and_reload()
        sync_text = (f"host syncs inside the dispatch (choose, command) in the replay batches: {syncs} "
                     f"(torch.cuda sync debug mode, a prototype that does not see every sync)" if checked else
                     "host syncs inside the dispatch: not checked (CPU: no host/device boundary)")
        place = checks["ctl_device_placement"]
        place["detail"] += f"; {sync_text}"
        if checked and syncs:
            place["status"] = FAIL
        self.controls.update(checks)
        if any(v["status"] != PASS for v in self.controls.values()):
            return self.fail()
        clips = self.clips()
        have = [c for c in clips if (self.a.run_dir / c.split(":")[0]).is_file()]
        self.controls["ctl_clips"] = {"status": PASS if len(have) == CLIP_GAMES else FAIL,
                                      "detail": f"{len(have)} clips of {CLIP_GAMES} (spec: two): " + "; ".join(clips)}
        stale = extra["stale"]
        nonfinite += int(extra["update_nonfinite"])
        self.controls["ctl_nonfinite_stale"] = {"status": PASS if nonfinite == 0 else NONFINITE,
                                                "detail": f"{nonfinite} non-finite actions or physics values; stale "
                                                          f"share {stale['detail']}"}
        if any(v["status"] != PASS for v in self.controls.values()):
            return self.fail(NONFINITE if nonfinite else FAIL)
        self.save_controls()
        what = ("STE L3.1 Isaac smoke of the tier-2 skills fixed-choice replay (scripts/ste_l3_isaac_smoke.py); "
                "observed in the training simulator")
        result = {"what": what, "status": STATUS,
                  "tier": ("reference world (--dry-cpu, not of record)" if self.a.dry_cpu else
                           "tier 2, Isaac Lab rigid-body Starling"),
                  "device": self.device, "games": self.n, "ticks_cap": self.ticks, "gates_sha256": g.sha256,
                  "replay": replay_rows, "throughput": throughput, "clips": clips, "upsets": upsets,
                  "of_record": of_record(g, self.a.dry_cpu, self.n, self.ticks),
                  "host_syncs_in_dispatch": sync_text,
                  "cuda_replay_tolerance": ("exercised only by the Isaac run on CUDA (exploit.replay_ok's CUDA "
                                            "tolerances); --dry-cpu plays the CPU game-for-game rule"),
                  "controls": {k: v["status"] for k, v in self.controls.items()}, "complete": True}
        from svg_training.ste import atomic
        atomic.write_text(self.a.run_dir / RESULTS, json.dumps(result, indent=1, sort_keys=True) + "\n")
        atomic.write_text(self.a.run_dir / "results.md", render(result))
        say(f"done: {self.a.run_dir / 'results.md'}")
        return 0

    def device_and_reload(self) -> tuple[dict, dict]:
        """Checks 2 and 3 -> (controls, extra): extra holds the update's stale share and non-finite count (check 5)."""
        import torch

        from svg_training.opponents.scripted import make_strategy
        from svg_training.ste import exploit_train, skills
        g, dev = self.gates, torch.device(self.device)
        game = exploit_train.TrainGame(self.cfg2, TRAIN_GAMES, 3, 3, device=self.device,
                                       seed=int(g.variants["base"]["train_seed"]["guard"]),
                                       world=self.view(TRAIN_GAMES))
        opp = make_strategy(self.ex.opponent_of(g, "base", "guard"), "strike", self.cfg2, TRAIN_GAMES, self.device, 1)
        env = exploit_train.decision_env(game, HOLD, "guard", opp, g.learner, g.players, 1)
        settings = {**g.trainer, "num_games": TRAIN_GAMES, "rollouts": 2, "learning_epochs": 1, "mini_batches": 1}
        learner = exploit_train.Learner(settings, env, self.device, seed=3)
        stats = learner.update()
        out: dict = {}
        extra = {"update_nonfinite": int(stats["nonfinite_actions"]),
                 "stale": {"detail": f"{float(stats['stale_tick_share']):.4f} of the update's ticks"}}
        obs = env._game_obs["guard"].clone()
        tensors = {"observations": obs, "team map": env.skills._team_map, "drone map": env.skills._drone_map}
        tensors.update({f"{a} policy": next(learner.agent.policies[a].parameters()) for a in learner.names})
        _, outs = learner.agent.act(learner.obs, learner.states, timestep=0, timesteps=1)
        tensors.update({f"{a} action": outs[a]["net_output"] for a in learner.names})
        wrong = [k for k, t in tensors.items() if t.device.type != dev.type]
        out["ctl_device_placement"] = {"status": PASS if not wrong else FAIL,
                                       "detail": f"{len(tensors)} tensors on {dev.type}" if not wrong else
                                       f"not on {dev.type}: {wrong}"}
        saved = learner.saved()
        path = self.a.run_dir / "reload_saved.pt"
        torch.save(saved, path)
        back = torch.load(path, map_location="cpu", weights_only=False)
        d_cpu = skills.two_level_dispatch(g.learner, g.players, "guard", self.cfg1, obs.shape[0], "cpu", 0)
        cpu_team = exploit_train.skill_team_from_modules("guard", back, list(g.trainer["hidden"]), d_cpu, "cpu")
        here = learner.team()
        l_dev, l_cpu = here.logits(obs).cpu(), cpu_team.logits(obs.cpu())
        diff = float((l_dev - l_cpu).abs().max())
        same = bool(torch.equal(env.skills.greedy(l_dev), d_cpu.greedy(l_cpu)))
        out["ctl_reload_across_devices"] = {"status": PASS if diff <= RELOAD_TOL and same else FAIL,
                                            "detail": f"{self.device} -> cpu: max |logit diff| {diff:.2e} (tol "
                                                      f"{RELOAD_TOL:g}), greedy choices equal {same}"}
        return out, extra

    def clips(self) -> list[str]:
        """Check 4: two clips of a fixed two-level Guard team (free + its first drone skill) on tier 2, CPU starts."""
        from svg_training.opponents.scripted import make_strategy
        from svg_training.ste import skills
        from svg_training.viz.replay import cpu_starts, record_games, render_replay
        g, v = self.gates, self.gates.videos
        seed = int(g.run["clip_seed"])
        d = skills.two_level_dispatch(g.learner, g.players, "guard", self.cfg2, CLIP_GAMES, self.device, 0)
        team = self.ex.HeldPlayer(self.team("guard", [(skills.FREE, 0)] * 3, d), HOLD)
        team.name = "fixed two-level Guard team (free + first drone skill)"
        opp = make_strategy(self.ex.opponent_of(g, "base", "guard"), "strike", self.cfg2, CLIP_GAMES, self.device, seed)
        starts = cpu_starts(self.cfg1, CLIP_GAMES, 3, 3, seed, band=0)
        recs = record_games(self.cfg2, 3, 3, team, opp, num_games=CLIP_GAMES, seed=seed, band=0,
                            max_steps=min(int(v["max_ticks"]), self.ticks), device=self.device,
                            world=self.view(CLIP_GAMES), starts=starts)
        out = []
        for rec in recs[:CLIP_GAMES]:                 # the spec's two clips: every clip game, ended or not
            kind = ("reach" if rec.outcome == self.ex.STRIKE_WIN else "hold" if rec.outcome == self.ex.GUARD_WIN
                    else "running")
            path = render_replay(rec, self.a.run_dir / "videos" / f"l3_smoke_tier2_game{rec.game_index}_{kind}.gif",
                                 speed=int(v["speed"]), fps=int(v["fps"]), dpi=int(v["dpi"]))
            out.append(f"videos/{path.name}: tier 2, game {rec.game_index}, {kind}")
        return out


class _Composite:
    """Drone m flies script ``names[m]`` (the oracle of the mixed "free" combinations, without the dispatch)."""

    def __init__(self, side, names, cfg, n, device):
        from svg_training.opponents.scripted import make_strategy
        self.team, self.name = side, "composite(" + ",".join(names) + ")"
        self.scripts = [make_strategy(nm, side, cfg, n, device, 0) for nm in names]

    def reset(self, games):
        for s in self.scripts:
            s.reset(games)

    def act(self, obs):
        import torch
        return torch.stack([s.act(obs)[:, m] for m, s in enumerate(self.scripts)], dim=1)


def render(r: dict) -> str:
    lines = [f"Simulator: {r['tier']}; {r['status']}; observed in the training simulator", "",
             "# L3.1 Isaac smoke: the tier-2 skills fixed-choice replay", "",
             f"{r['games']} games per cell, {r['ticks_cap']} ticks, device {r['device']}.", "",
             "| Control | Status |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(r["controls"].items())]
    th = r["throughput"]
    lines += ["", f"Throughput: two-level team {th['two_level_game_steps_per_s']:,.0f} game-steps/s, one script "
                  f"{th['one_script_game_steps_per_s']:,.0f}; ratio {th['ratio']:.3f} (spec B1)", "",
              "Clips: " + "; ".join(r["clips"]), "", f"Of record: {r['of_record']}. Upsets: {r['upsets']}.",
              f"Device: {r['host_syncs_in_dispatch']}. CUDA replay tolerance: {r['cuda_replay_tolerance']}."]
    return "\n".join(lines) + "\n"


def _isaac_cli() -> int:
    """Isaac Sim starts headless before torch is imported; the process leaves through os._exit (as L1.8, L2.6)."""
    code = 1
    try:
        from _isaac_app import start_headless
        args, _app = start_headless(parser(isaac=True))
        args.headless = True
        code = run(args)
    except KeyboardInterrupt:
        code = 4
    except SystemExit as ex:
        code = ex.code if isinstance(ex.code, int) else 2
    except BaseException:  # noqa: BLE001
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
    return code


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--dry-cpu" not in argv:
        problem = pre_isaac_problem(argv)
        if problem:
            print(f"refused: {problem[1]}" if problem[0] == 2 else problem[1], file=sys.stderr)
            sys.exit(problem[0])
        _isaac_cli()
    sys.exit(main())
