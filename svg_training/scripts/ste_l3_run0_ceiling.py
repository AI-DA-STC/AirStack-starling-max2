#!/usr/bin/env python
"""STE phase L3: the constant-choice ceiling of the skills route's run 0 (addendum of 25 Nov 2026 to
ste_learning/drafts/L3_SLICE2_DESIGN.md "Run 0 for the skills route"; spec drafts/L3_L6_PIPELINE_SPEC.md). Scoring only,
no training.

    ste_l3_run0_ceiling.py --out <folder> [--gates configs/ste_l3/skills_gates.toml] [--games <n>]
                           [--device cpu|cuda] [--chunk <choices per batch>]
    ste_l3_run0_ceiling.py --oracle-check <finished ceiling folder> [--top 3] [--check-out <file>]

Why: run 0's mark ``[run0] skills_reach_min`` was set at 0.90 from the 1v1 screen (T66). In the 3v3 base game on T44's
starts the parked-centre Guard holds against every Strike script (T70, the L2.5 screen, group ctl_reference_replay;
the Guard's HOLDS of 1,000: straight 534, flank 450, high 466, low 430, sacrifice 525, converge 986), so no script
reaches above 570 (reaches = 1,000 - holds; no game was unfinished). This script
measures what the best CONSTANT choice of the two-level Strike team reaches, so the mark can be re-set by the rule
fixed before this run: skills_reach_min = (best reaches - [run0] margin x n) / n, required above the untrained team's
Wilson upper bound (else the lead re-plans).

Every constant choice of the two-level Strike team (the gate file's ``[learner]`` lists): each team strategy, and under
"free" each per-drone combination of the drone skills (K_d ** M of them, M Strike drones), held for the whole game
against ``[run0] opponent`` on T44's first ``--games`` starts, through the scoring path run 0 uses:
``exploit.play_cells`` with a ``SkillTeam`` per choice (a constant-logit network per drone slot) over the
``TwoLevelDispatch``, held ``decision_ticks`` by ``HeldPlayer`` (it holds the CHOICE; the chosen skill flies closed
loop). Batched: every choice of a chunk plays in one game batch (``--chunk`` choices; default all).

Controls (exit 6, nothing but controls.json written, on a failure; 5 on a non-finite action):
``ctl_one_script_choices_are_reference`` (a choice that flies one script on every drone, i.e. each team strategy and
each free same-skill choice, equals T44's cell of that script game for game, ``exploit.replay_ok`` with the game cap);
``ctl_choice_log_is_the_fixed_choice`` (the held choice log shows only the choice's players, and at the first decision
each player once per drone that flies it per game); and the plumbing controls (paired starts, one for one, no
non-finite action) of every batch.

Writes <out>/controls.json, results.json (per choice: reaches k of n with the Wilson 95 % interval, holds, unfinished;
the best; the untrained team; the mark rule's numbers; ``of_record``, true only for 1,000 games on the CPU, the device
of record; ``complete`` last) and results.md. Exit codes: 0 done; 2 refused
(bad arguments, a finished folder, a gate file that is not the two-level skills route, an input off its pin); 5 a
non-finite action; 6 a control failed. Launched through scripts/ste_job.py (it records exit_code). Training simulator,
tier 1: results are "observed in the training simulator"; a pipeline check, not for flight.

``--oracle-check`` (lead's QC S1, 25 Nov 2026), on a finished ceiling folder, before the mark is accepted: the best
choice and the ``--top`` choices by reaches (choice order on a tie) are replayed on the CPU at the folder's n through the
dispatch and against the hold-1 oracle written without the dispatch (``Composite``: drone m flies its script's own
column, closed loop). PASS needs every game equal (outcome, end step, tags, Strike drones left) and the replay's reaches
equal to the folder's. Writes <folder>/oracle_check.json (or ``--check-out``), ``complete`` last; exit 0 PASS, 6 FAIL,
2 refused (no finished ceiling, a finished check, a gate file off the folder's sha256)."""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch import nn  # noqa: E402

import ste_l3_held_arm as arm  # noqa: E402  (the input checks against the gate file's pins)
import ste_sweep_l011 as l011  # noqa: E402  (the simulator label, JSON writing)
from svg_training.core.metrics import wilson_interval  # noqa: E402
from svg_training.opponents.scripted import make_strategy  # noqa: E402
from svg_training.ste import atomic, exploit, scoring, skills, sweep  # noqa: E402

EXIT_DONE, EXIT_REFUSED, EXIT_CONTROL_FAILED = 0, 2, 6
PASS, FAIL = scoring.PASS, scoring.FAIL
SIDE = "strike"
VARIANT = "base"                    # the gate file's [run0] variant is read; this is only the fallback name
DEFAULT_GATES = ROOT / "configs" / "ste_l3" / "skills_gates.toml"
TEAM_KIND, FREE_KIND = "team", "free"
MARK_SET, LEAD_RE_PLANS, NOT_OF_RECORD = "MARK_SET", "LEAD_RE_PLANS", "NOT_OF_RECORD"
ORACLE_FILE = "oracle_check.json"
ORACLE = "oracle:"                  # the oracle's cell name (never a script's or a choice's name)
TOP = 3                             # --oracle-check: the top choices replayed besides the best
STATUS = "pipeline check, not for flight"


class ConstHeads(nn.Module):
    """A constant two-level network: logits [B, T + 1 + K_d] with 1 at team index ``t`` and at drone index ``d``, 0
    elsewhere, whatever the observation [B, D] (the dispatch's argmax then plays (t, d) every decision)."""

    def __init__(self, t: int, d: int, widths: tuple[int, int]):
        super().__init__()
        self.t, self.d, self.widths = int(t), int(d), tuple(widths)

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        out = obs.new_zeros(obs.shape[0], sum(self.widths))
        out[:, self.t] = 1.0
        out[:, self.widths[0] + self.d] = 1.0
        return out


def strikes(gates) -> int:
    return int(sweep.parse_size(gates.run["size"])[1])


def choices(gates) -> list[dict]:
    """Every constant choice of the Strike team, in a fixed order: the team strategies (team head t >= 1, drone head 0,
    which a team strategy never reads), then under "free" (team head 0) every per-slot combination of the drone skills
    (slot 0 the slowest-changing digit). Each: name, kind, heads [(t, d)] per slot, flies [player per slot], script (the
    one script every drone flies, or None)."""
    m = strikes(gates)
    team = list(gates.learner.team_strategies[SIDE])
    drone = list(gates.learner.drone_skills[SIDE])
    out = [{"name": f"team:{s}", "kind": TEAM_KIND, "heads": [(t, 0)] * m, "flies": [s] * m, "script": s}
           for t, s in enumerate(team, start=1)]
    for combo in itertools.product(range(len(drone)), repeat=m):
        flies = [drone[d] for d in combo]
        out.append({"name": "free:" + "+".join(flies), "kind": FREE_KIND,
                    "heads": [(skills.FREE, d) for d in combo], "flies": flies,
                    "script": flies[0] if len(set(flies)) == 1 else None})
    return out


def untrained_choice(chs: list[dict], gates) -> dict:
    """The untrained two-level team's play (p(free) = 0.5, the argmax free + the first drone skill on every drone)."""
    first = gates.learner.drone_skills[SIDE][0]
    return next(c for c in chs if c["kind"] == FREE_KIND and c["flies"] == [first] * strikes(gates))


def fixed_team(gates, choice: dict, cfg, n: int, device: str, seed: int) -> exploit.SkillTeam:
    """The Strike ``SkillTeam`` that plays ``choice`` every decision over ``n`` games: the real two-level dispatch of
    the gate file's lists, a constant network per drone slot, identity scalers."""
    d = skills.two_level_dispatch(gates.learner, gates.players, SIDE, cfg, n, device, seed)
    nets = [ConstHeads(t, k, d.widths).to(device) for t, k in choice["heads"]]
    return exploit.SkillTeam(SIDE, nets, [lambda o, train=False: o] * len(nets), d, name=choice["name"])


def _merge(parts: list[dict]) -> dict:
    """The plumbing controls of every batch, one entry per control: the worst status, the details joined."""
    out = {}
    for part in parts:
        for key, v in part.items():
            if key not in out:
                out[key] = dict(v)
                continue
            have = out[key]
            rank = {PASS: 0, FAIL: 1, scoring.NONFINITE: 2}
            if rank.get(v["status"], 1) > rank.get(have["status"], 1):
                have["status"] = v["status"]
            have["detail"] = f"{have['detail']}; {v['detail']}"
    return out


def play(gates, ref, chs: list[dict], n: int, device: str, chunk: int) -> dict:
    """Play ``chs`` against [run0] opponent on T44's first ``n`` starts, ``chunk`` choices per game batch. Returns
    {"cells": per choice the per-game arrays, "logs": per choice the held choice log [decisions, players],
    "plumbing": the merged plumbing controls}."""
    variant = gates.run0.get("variant", VARIANT)
    cfg = exploit.variant_cfg(gates, variant)
    opp = gates.run0["opponent"]
    seed, cap, hold = int(ref.meta["seed"]), int(gates.run["ticks_cap"]), int(gates.trainer["decision_ticks"])
    cells, logs, plumbing = [], [], []
    for lo in range(0, len(chs), chunk):
        part = chs[lo:lo + chunk]
        players = {c["name"]: fixed_team(gates, c, cfg, n, device, seed + exploit.STRIKE_SEED_OFFSET) for c in part}
        pg = exploit.play_cells(cfg, gates.run["size"], ref, [(opp, c["name"]) for c in part], n, device, seed, cap,
                                hold_ticks=hold, players=players)
        for k in range(len(part)):
            cells.append(exploit.slice_cell(pg, k, n))
            logs.append(pg["choice_log"][(SIDE, k)])
        plumbing.append(scoring.plumbing_controls(pg, ref, n, "ceiling"))
        print(f"[ceiling] played choices {lo + 1}-{lo + len(part)} of {len(chs)} ({n} games each)", flush=True)
    return {"cells": cells, "logs": logs, "plumbing": _merge(plumbing)}


def controls_of(gates, ref, chs: list[dict], played: dict, n: int, device: str) -> dict:
    """The run's controls (module docstring)."""
    rv = exploit.ref_variant(gates, gates.run0.get("variant", VARIANT))
    opp, cap = gates.run0["opponent"], int(gates.run["ticks_cap"])
    rows = []
    for c, cell in zip(chs, played["cells"]):
        if c["script"] is None:
            continue
        t44 = {k: np.asarray(v)[:n] for k, v in ref.cell(rv, opp, c["script"]).items()}
        good, text = exploit.replay_ok(cell, t44, device, gates.controls, ticks_cap=cap)
        rows.append((c["name"], good, text))
    out = {"ctl_one_script_choices_are_reference": {
        "status": PASS if rows and all(r[1] for r in rows) else FAIL, "phase": "ceiling",
        "detail": "; ".join(f"{name} v T44's cell {'ok' if good else 'DIFFERS'} ({text})" for name, good, text in rows)
                  or "no choice flies one script"}}
    names = skills.team_skills(gates.players, SIDE)
    bad = []
    for c, log in zip(chs, played["logs"]):
        log = np.asarray(log)
        allowed = {names.index(s) for s in c["flies"]}
        outside = [names[j] for j in range(log.shape[1]) if j not in allowed and log[:, j].sum()]
        first = {names[j]: int(log[0, j]) for j in allowed}
        want = {s: n * c["flies"].count(s) for s in set(c["flies"])}
        if outside or first != want:
            bad.append(f"{c['name']}: outside {outside}, first decision {first} v {want}")
    out["ctl_choice_log_is_the_fixed_choice"] = {
        "status": FAIL if bad else PASS, "phase": "ceiling",
        "detail": "; ".join(bad) if bad else f"every choice ({len(chs)}) flew only its own players; at the first "
                                             f"decision each player once per drone that flies it, per game"}
    out.update(played["plumbing"])
    return out


def mark_rule(k_best: int, k_untrained: int, n: int, margin: float, *, of_record: bool) -> dict:
    """The mark rule fixed before the run (addendum of 25 Nov 2026): mark = best constant choice's reaches less
    ``margin`` x n, as a count of the n evaluation games (so the read ``k / n >= mark`` has no float edge); it must lie
    above the untrained team's Wilson 95 % upper bound, else the lead re-plans (no mark is set by this rule).
    ``of_record`` False (QC S4): status NOT_OF_RECORD and no ``toml_value``; the arithmetic is still shown."""
    mark_count = int(k_best) - int(round(float(margin) * n))
    hi = wilson_interval(int(k_untrained), n)[1]
    mark = mark_count / n
    above = bool(mark > hi)
    return {"rule": "skills_reach_min = (best constant-choice reaches - margin x n) / n, above the untrained team's "
                    "Wilson 95 % upper bound", "margin": float(margin), "n": int(n), "k_best": int(k_best),
            "mark_count": mark_count, "skills_reach_min": mark, "toml_value": f"{mark:.3f}" if of_record else None,
            "untrained_k": int(k_untrained), "untrained_ci_high": hi, "mark_above_untrained_high": above,
            "status": (MARK_SET if above else LEAD_RE_PLANS) if of_record else NOT_OF_RECORD}


def of_record(n: int, device: str) -> bool:
    """The ceiling of record (addendum of 25 Nov 2026): run 0's 1,000 evaluation games on the CPU (the device of record:
    it replays T44 exactly; a CUDA run agrees only within the CUDA tolerance and is INFO)."""
    return bool(int(n) == exploit.SKILLS_RUN0_EVAL_GAMES and str(device) == "cpu")


def row(c: dict, cell: dict, n: int) -> dict:
    outcome = np.asarray(cell["outcome"])
    k = int(np.sum(outcome == exploit.STRIKE_WIN))
    return {"name": c["name"], "kind": c["kind"], "flies": c["flies"], "heads": [list(h) for h in c["heads"]],
            "script": c["script"], "k": k, "n": int(n), "rate": k / n, "ci": list(wilson_interval(k, n)),
            "holds": int(np.sum(outcome == exploit.GUARD_WIN)), "unfinished": int(np.sum(outcome == exploit.RUNNING))}


class Composite:
    """The oracle, written without the dispatch: drone m flies script ``names[m]`` closed loop (its own column of that
    script's command on the whole team's observation [N, M, D] -> [N, M, 4])."""

    def __init__(self, names: list[str], cfg, n: int, device: str = "cpu", seed: int = 0):
        self.team, self.name = SIDE, ORACLE + "+".join(names)
        self.scripts = [make_strategy(nm, SIDE, cfg, n, device, seed) for nm in names]

    def reset(self, games: torch.Tensor) -> None:
        for s in self.scripts:
            s.reset(games)

    def act(self, obs: torch.Tensor) -> torch.Tensor:
        return torch.stack([s.act(obs)[:, m] for m, s in enumerate(self.scripts)], dim=1)


def oracle_check(folder: Path, out: Path | None, top: int) -> int:
    """The oracle check of a finished ceiling folder (module docstring; QC S1)."""
    res_file, out = folder / "results.json", (out if out is not None else folder / ORACLE_FILE)
    try:
        res = json.loads(res_file.read_text())
    except (OSError, ValueError):
        res = {}
    if not res.get("complete"):
        return refuse(f"{folder} holds no finished ceiling ({res_file} with complete: true)")
    if out.exists():
        return refuse(f"{out} exists: the check is done (a new check needs another --check-out)")
    if top < 1:
        return refuse(f"--top must be at least 1, got {top}")
    gfile = Path(res["gates_file"])
    gfile = gfile if gfile.is_absolute() or gfile.is_file() else ROOT / gfile
    try:
        gates = exploit.load_gates(gfile)
    except (OSError, ValueError) as err:
        return refuse(f"gate file {gfile}: {err}")
    if gates.sha256 != res["gates_sha256"]:
        return refuse(f"gate file {gfile} has sha256 {gates.sha256[:12]}, the ceiling ran under "
                      f"{res['gates_sha256'][:12]}")
    problem = arm.input_problems(gates)
    if problem:
        return refuse(problem)
    ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
    n, device = int(res["games"]), "cpu"
    ranked = sorted(res["choices"], key=lambda c: -c["k"])          # stable: choice order on a tie
    names = list(dict.fromkeys([res["best"]["name"]] + [c["name"] for c in ranked[:top]]))
    by_name = {c["name"]: c for c in choices(gates)}
    chs = [by_name[nm] for nm in names]
    print(f"[oracle check] {folder}: {names}, {n} games each, {device}", flush=True)
    replay = play(gates, ref, chs, n, device, chunk=len(chs))["cells"]
    cfg = exploit.variant_cfg(gates, gates.run0.get("variant", VARIANT))
    seed = int(ref.meta["seed"])
    players = {ORACLE + c["name"]: Composite(c["flies"], cfg, n, device, seed + exploit.STRIKE_SEED_OFFSET)
               for c in chs}
    pg = exploit.play_cells(cfg, gates.run["size"], ref, [(gates.run0["opponent"], ORACLE + c["name"]) for c in chs],
                            n, device, seed, int(gates.run["ticks_cap"]), hold_ticks=1, players=players)
    k_ceiling = {c["name"]: c["k"] for c in res["choices"]}
    rows = []
    for i, c in enumerate(chs):
        mine, oracle = replay[i], exploit.slice_cell(pg, i, n)
        rows.append({"name": c["name"], "flies": c["flies"], "games": n,
                     "differ": int(exploit.agreement(mine, oracle)["differ"]),
                     "k_replay": int(np.sum(np.asarray(mine["outcome"]) == exploit.STRIKE_WIN)),
                     "k_oracle": int(np.sum(np.asarray(oracle["outcome"]) == exploit.STRIKE_WIN)),
                     "k_ceiling": int(k_ceiling[c["name"]])})
    ok = all(r["differ"] == 0 and r["k_replay"] == r["k_ceiling"] for r in rows)
    chk = {"what": "STE L3 oracle check of the run 0 ceiling (scripts/ste_l3_run0_ceiling.py --oracle-check): the best "
                   "and top choices through the dispatch v the hold-1 oracle without it; observed in the training "
                   "simulator", "status_note": STATUS, "folder": str(folder), "games": n, "device": device,
           "top": top, "ceiling_gates_sha256": res["gates_sha256"], "of_record": bool(res.get("of_record")),
           "status": PASS if ok else FAIL, "checked": rows}
    chk["complete"] = True                                       # written last
    l011.write_json(out, chk)
    print(f"[oracle check] {chk['status']}: " + "; ".join(f"{r['name']} differ {r['differ']}, k {r['k_replay']} v "
                                                          f"oracle {r['k_oracle']} v ceiling {r['k_ceiling']}"
                                                          for r in rows), flush=True)
    return EXIT_DONE if ok else EXIT_CONTROL_FAILED


def refuse(why: str) -> int:
    print(f"refused: {why}", file=sys.stderr)
    return EXIT_REFUSED


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ste_l3_run0_ceiling.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, help="the ceiling's folder (the ceiling run)")
    ap.add_argument("--gates", type=Path)
    ap.add_argument("--games", type=int, help="T44's first n starts (default: the gate file's eval_games)")
    ap.add_argument("--device")
    ap.add_argument("--chunk", type=int, help="choices per game batch (default: all in one batch)")
    ap.add_argument("--oracle-check", type=Path, help="a finished ceiling folder: the oracle check (QC S1)")
    ap.add_argument("--top", type=int, default=TOP, help="--oracle-check: top choices replayed besides the best")
    ap.add_argument("--check-out", type=Path, help=f"--oracle-check: the result file (default <folder>/{ORACLE_FILE})")
    a = ap.parse_args(argv)
    if a.oracle_check is not None:
        if any(v is not None for v in (a.out, a.gates, a.games, a.device, a.chunk)):
            return refuse("--oracle-check takes only --top and --check-out (it reads the rest from the folder)")
        return oracle_check(a.oracle_check, a.check_out, a.top)
    if a.out is None:
        return refuse("--out <folder> (a ceiling run) or --oracle-check <folder> (the check of a finished one)")
    a.gates = a.gates if a.gates is not None else DEFAULT_GATES
    a.device = a.device if a.device is not None else "cpu"
    try:
        gates = exploit.load_gates(a.gates)
    except (OSError, ValueError) as err:
        return refuse(f"gate file {a.gates}: {err}")
    if not (gates.learner.skills and gates.learner.choice == skills.TWO_LEVEL):
        return refuse(f"{a.gates} is not the two-level skills route ([learner] action = \"skills\", choice = "
                      f"\"{skills.TWO_LEVEL}\")")
    problem = arm.input_problems(gates)
    if problem:
        return refuse(problem)
    ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
    n = int(a.games if a.games is not None else gates.run["eval_games"])
    chs = choices(gates)
    chunk = int(a.chunk if a.chunk is not None else len(chs))
    if not 1 <= n <= ref.games:
        return refuse(f"--games must be 1..{ref.games} (the reference's starts), got {n}")
    if chunk < 1:
        return refuse(f"--chunk must be at least 1, got {chunk}")
    if (a.out / "results.json").is_file():
        return refuse(f"{a.out} holds a finished ceiling (results.json): a new run needs a new folder")
    a.out.mkdir(parents=True, exist_ok=True)
    print(f"[ceiling] {len(chs)} constant choices x {n} games v {gates.run0['opponent']}, {chunk} per batch, "
          f"{a.device}; gate sha256 {gates.sha256[:12]}", flush=True)
    played = play(gates, ref, chs, n, a.device, chunk)
    controls = controls_of(gates, ref, chs, played, n, a.device)
    l011.write_json(a.out / "controls.json", controls)
    code = scoring.ending(controls)
    if code is not None:
        print(f"CONTROL FAILED: {[k for k, v in controls.items() if v['status'] != PASS]}; nothing published "
              f"(exit {code})", file=sys.stderr)
        return code
    rows = [row(c, cell, n) for c, cell in zip(chs, played["cells"])]
    best = max(rows, key=lambda r: r["k"])                      # the first in choice order on a tie
    unt = next(r for r in rows if r["name"] == untrained_choice(chs, gates)["name"])
    result = {"what": "STE L3 constant-choice ceiling of the skills route's run 0 (scripts/ste_l3_run0_ceiling.py): "
                      "every constant choice of the two-level Strike team v the run 0 Guard; observed in the training "
                      "simulator", "status_note": STATUS, "simulator": l011.SIMULATOR,
              "variant": gates.run0.get("variant", VARIANT), "opponent": gates.run0["opponent"],
              "size": gates.run["size"], "games": n, "hold_ticks": int(gates.trainer["decision_ticks"]),
              "ticks_cap": int(gates.run["ticks_cap"]), "device": a.device, "chunk": chunk,
              "gates_file": str(a.gates), "gates_sha256": gates.sha256, "reference_sha256": gates.reference["sha256"],
              "learner": skills.learner_table(gates.learner),
              "of_record": of_record(n, a.device),
              "current_mark": gates.run0.get("skills_reach_min"),
              "controls": controls, "choices": rows,
              "best": {k: best[k] for k in ("name", "flies", "k", "n", "rate", "ci")},
              "untrained": {k: unt[k] for k in ("name", "flies", "k", "n", "rate", "ci")},
              "mark": mark_rule(best["k"], unt["k"], n, float(gates.run0["margin"]),
                                of_record=of_record(n, a.device))}
    result["complete"] = True                                    # written last
    atomic.write_text(a.out / "results.md", render(result))
    l011.write_json(a.out / "results.json", result)
    print(f"[ceiling] best {best['name']} {best['k']}/{n}; mark {result['mark']['toml_value']} "
          f"({result['mark']['status']}): {a.out / 'results.md'}", flush=True)
    return EXIT_DONE


def render(r: dict) -> str:
    mk = r["mark"]
    lines = [f"Simulator: {r['simulator']}", "",
             f"# Run 0 constant-choice ceiling, skills route: Strike v {r['opponent']} ({r['size']}, {r['variant']})",
             "", f"{r['games']} games per choice on T44's starts, the choice held every {r['hold_ticks']}-tick "
                 f"decision for the whole game; device {r['device']}; {STATUS}; of record: {r['of_record']}.", "",
             f"- Best constant choice: **{r['best']['name']}** {r['best']['k']}/{r['games']} "
             f"(95 % CI {r['best']['ci'][0]:.3f}-{r['best']['ci'][1]:.3f})",
             f"- Untrained team ({r['untrained']['name']}): {r['untrained']['k']}/{r['games']}, Wilson upper bound "
             f"{mk['untrained_ci_high']:.4f}",
             f"- Mark rule: ({mk['k_best']} - {mk['margin']} x {mk['n']}) / {mk['n']} = {mk['mark_count']}/{mk['n']} "
             f"= **{mk['toml_value']}**; above the untrained upper bound: {mk['mark_above_untrained_high']} "
             f"(**{mk['status']}**); the gate file's mark now: {r['current_mark']}",
             "", "| Choice | Flies (slot 0, 1, 2) | Reaches | 95 % CI | Holds | Unfinished |",
             "|---|---|---|---|---|---|"]
    for c in sorted(r["choices"], key=lambda c: -c["k"]):
        lines.append(f"| {c['name']} | {', '.join(c['flies'])} | {c['k']}/{c['n']} | {c['ci'][0]:.3f}-{c['ci'][1]:.3f} "
                     f"| {c['holds']} | {c['unfinished']} |")
    lines += ["", "Controls: " + "; ".join(f"{k} {v['status']}" for k, v in r["controls"].items())]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
