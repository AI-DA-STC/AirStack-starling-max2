#!/usr/bin/env python
"""STE L3-L6 pipeline check, task L4.2: the scoring suite on known players, before any trained run (spec
ste_learning/drafts/L3_L6_PIPELINE_SPEC.md section 3: required before the route comparison is written). CPU by
default; launched through ``scripts/ste_job.py`` (--task L4.2, --run-dir <out>). No training.

    ste_l4_suite.py --out <folder> [--games <n>] [--routes velocity,skills] [--sides guard,strike] [--device cpu]

For each route's pre-registered gate file (``configs/ste_l3/<route>_gates.toml``) and each side, ONE batch through the
final-scoring path of ``scripts/ste_exploit_l012.py`` (``exploit.play_cells`` on T44's first ``--games`` starts, the
learner held ``decision_ticks``, then ``pool_block``: the pooled row with its per-start standard error, the best single
fixed choice, the choice share). The players are known:

* the route's untrained team (velocity: zero-mean, so still; skills: "free" + the first drone skill for every drone)
  against every script of the other team (the cells a trained run's INFO batch plays);
* its twin cells (velocity: the ``zero`` script; skills: the first drone skill);
* a script team (the side's first script) against every script of the other team.

Checks (each PASS / FAIL, in ``suite_check.json``):
``ctl_untrained_is_known`` (each untrained cell equals its twin game for game, ``exploit.replay_ok``);
``ctl_script_cells_are_reference`` (each script cell equals T44's cell game for game);
``ctl_pooled_row_of_the_script_team`` (``scoring.pooled_row`` on the played script cells equals the exact mean of
T44's cell rates and the standard error of T44's per-start means);
``ctl_pooled_row_of_the_untrained_team`` (``pool_block``'s pooled row equals that of the twin cells);
``ctl_best_single_choice`` (``pool_block``'s best equals the best by T44's pooled rates, computed here on its own);
``ctl_choice_share`` (skills: every logged decision flew the first drone skill, share 1 in every bin with decisions;
velocity: no choice share is written); and the plumbing controls (paired starts, one for one, no non-finite action).

Writes <out>/suite_check.json ({"complete": true, "status": "PASS" | "FAIL", "checks", "games", "gates_sha256"}),
the file ``scripts/ste_l6_read.py`` reads, and suite_check.md. Exit codes: 0 PASS; 2 refused (a finished folder, bad
arguments); 6 a check failed (the file is written, status FAIL). Pipeline check, not for flight; observed in the
training simulator."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402

import ste_exploit_l012 as driver  # noqa: E402  (the final-scoring path: info_cells, per_cell, pool_block)
from svg_training.ste import exploit, exploit_train, pool, scoring, skills, sweep  # noqa: E402

EXIT_DONE, EXIT_REFUSED, EXIT_CONTROL_FAILED = 0, 2, 6
PASS, FAIL = "PASS", "FAIL"
STATUS = "pipeline check, not for flight"
ROUTES, SIDES = ("velocity", "skills"), ("guard", "strike")
GATE_DIR = ROOT / "configs" / "ste_l3"
OUT_FILE = "suite_check.json"
EXACT_TOL = 1e-12          # two exact means of the same 0/1 numbers, summed in another order
VARIANT = "base"


def refuse(why: str) -> int:
    print(f"refused: {why}", file=sys.stderr)
    return EXIT_REFUSED


def untrained(gates, side: str, n: int, device: str):
    """The route's team at its start, as the pilot and a run's "before" batch build it."""
    guards, strikes = sweep.parse_size(gates.run["size"])
    drones = guards if side == "guard" else strikes
    hidden = list(gates.trainer["hidden"])
    if gates.learner.skills:
        d = skills.two_level_dispatch(gates.learner, gates.players, side, exploit.variant_cfg(gates, VARIANT), n,
                                      device, 0)
        return exploit_train.untrained_skill_team(side, d, drones, hidden, device)
    return exploit.LearnerTeam.untrained(side, drones, hidden, device)


def same(a: float, b: float) -> bool:
    return (math.isnan(a) and math.isnan(b)) or abs(a - b) <= EXACT_TOL


def check(ok: bool, detail: str) -> dict:
    return {"status": PASS if ok else FAIL, "phase": "suite", "detail": detail}


def suite_side(gates, side: str, n: int, device: str, ref) -> dict:
    other = "strike" if side == "guard" else "guard"
    cfg = exploit.variant_cfg(gates, VARIANT)
    rv = exploit.ref_variant(gates, VARIANT)
    cap, hold = int(gates.run["ticks_cap"]), int(gates.trainer["decision_ticks"])
    won = exploit.STRIKE_WIN if side == "strike" else exploit.GUARD_WIN
    info = driver.info_cells(gates, side)
    script = (gates.learner.drone_skills[side][0] if gates.learner.skills
              else skills.team_skills(gates.players, side)[0])
    twin_name = gates.learner.drone_skills[side][0] if gates.learner.skills else exploit.ZERO

    def sub(name):
        return [tuple(name if x == exploit.EXPLOITER else x for x in c) for c in info]
    twins, script_cells = sub(twin_name), sub(script)
    cells = list(dict.fromkeys(info + twins + script_cells))
    pg = exploit.play_cells(cfg, gates.run["size"], ref, cells, n, device, ref.meta["seed"], cap,
                            learner=untrained(gates, side, n, device), hold_ticks=hold)
    cell_pg = driver.per_cell(pg, cells, n)
    block = driver.pool_block(gates, VARIANT, side, pg, info, n, ref)
    opp = (lambda c: c[0]) if side == "strike" else (lambda c: c[1])
    members = pool.pool_members(gates.players, other)
    out = {}

    rows = [(c, t, *exploit.replay_ok(cell_pg[c], cell_pg[t], device, gates.controls)) for c, t in zip(info, twins)]
    out["ctl_untrained_is_known"] = check(
        all(r[2] for r in rows), f"untrained team v its twin {twin_name} (replay text: 'T44' = the twin): " +
        "; ".join(f"{opp(c)} {'ok' if good else 'DIFFERS'} ({text})" for c, _, good, text in rows))

    ref_cell = {c: {k: np.asarray(v)[:n] for k, v in ref.cell(rv, *c).items()} for c in script_cells}
    rows = [(c, *exploit.replay_ok(cell_pg[c], ref_cell[c], device, gates.controls, ticks_cap=cap))
            for c in script_cells]
    out["ctl_script_cells_are_reference"] = check(all(r[1] for r in rows), f"{script} v each script: " + "; ".join(
        f"{opp(c)} {'ok' if good else 'DIFFERS'} ({text})" for c, good, text in rows))

    played = scoring.pooled_row({opp(c): cell_pg[c]["outcome"] == won for c in script_cells if opp(c) in members})
    y = np.mean([ref_cell[c]["outcome"] == won for c in script_cells if opp(c) in members], axis=0)
    want_rate = float(np.mean([np.mean(ref_cell[c]["outcome"] == won) for c in script_cells if opp(c) in members]))
    want_se = float(np.std(y, ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
    out["ctl_pooled_row_of_the_script_team"] = check(
        same(played["rate"], want_rate) and same(played["se"], want_se),
        f"{script}: pooled {played['rate']:.6f} (se {played['se']:.6f}) v T44's mean of cell rates {want_rate:.6f} "
        f"(se {want_se:.6f}) over {members}")

    twin_row = scoring.pooled_row({opp(c): cell_pg[c]["outcome"] == won for c in twins if opp(c) in members})
    got = block.get("pooled", {})
    out["ctl_pooled_row_of_the_untrained_team"] = check(
        bool(got) and same(got["rate"], twin_row["rate"]) and same(got["se"], twin_row["se"]),
        f"final-scoring pooled row {got.get('rate')} (se {got.get('se')}) v the twin cells' {twin_row['rate']} "
        f"(se {twin_row['se']})")

    rates = {}
    for s in skills.team_skills(gates.players, side):
        per = [np.mean(np.asarray(ref.cell(rv, *((o, s) if side == "strike" else (s, o)))["outcome"][:n]) == won)
               for o in members]
        rates[s] = float(np.mean(per))
    best = max(rates, key=lambda s: rates[s])                         # first on a tie, as scoring.best_single_choice
    bsc = block.get("best_single_choice", {})
    out["ctl_best_single_choice"] = check(
        bsc.get("best") == best and same(bsc["per_choice"][best]["rate"], rates[best]),
        f"final-scoring best {bsc.get('best')} v T44's best {best} ({rates[best]:.6f}); T44's pooled rates "
        + ", ".join(f"{s} {r:.4f}" for s, r in rates.items()))

    if gates.learner.skills:
        first, bad, total = gates.learner.drone_skills[side][0], [], 0
        for o, e in block.get("choice_by_decision", {}).items():
            total += sum(e["counts"])
            for j, c in enumerate(e["counts"]):
                if c and any((e["share"][k][j] != (1.0 if k == first else 0.0)) for k in e["share"]):
                    bad.append(f"{o} bin {e['bins'][j]}")
        ok = bool(block.get("choice_by_decision")) and total > 0 and not bad
        out["ctl_choice_share"] = check(ok, f"skills route: every logged decision ({total}) flew {first}, share 1 in "
                                            f"every bin with decisions" + (f"; not in {bad}" if bad else ""))
    else:
        ok = "choice_by_decision" not in block
        out["ctl_choice_share"] = check(ok, "velocity route: no choice share written (no skills)" if ok else
                                        "velocity route: a choice share was written")
    for k, v in scoring.plumbing_controls(pg, ref, n, "suite").items():
        out[k] = {**v, "status": PASS if v["status"] == PASS else FAIL}
    return out


def render(res: dict) -> str:
    lines = [f"Simulator: tier 1 training simulator (CPU reference play); {STATUS}. Observed in the training "
             f"simulator.", "", f"STE L4.2 scoring suite on known players, {res['games']} starts: **{res['status']}**",
             "", "| Route | Side | Check | Status | Detail |", "|---|---|---|---|---|"]
    for route, sides in res["checks"].items():
        for side, checks in sides.items():
            lines += [f"| {route} | {side} | {k} | {v['status']} | {v['detail'][:200]} |" for k, v in checks.items()]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ste_l4_suite.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--games", type=int, help="T44's first n starts (default: the gate file's eval_games)")
    ap.add_argument("--routes", default=",".join(ROUTES))
    ap.add_argument("--sides", default=",".join(SIDES))
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args(argv)
    if (a.out / OUT_FILE).exists():
        return refuse(f"{a.out} holds {OUT_FILE}: a new suite needs a new folder")
    routes = [r.strip() for r in a.routes.split(",") if r.strip()]
    sides = [s.strip() for s in a.sides.split(",") if s.strip()]
    if not routes or set(routes) - set(ROUTES) or not sides or set(sides) - set(SIDES):
        return refuse(f"--routes {a.routes} / --sides {a.sides}: from {ROUTES} / {SIDES}")
    gates = {r: exploit.load_gates(GATE_DIR / f"{r}_gates.toml") for r in routes}
    refs = {r: exploit.load_reference(exploit.ROOT / g.reference["file"]) for r, g in gates.items()}
    n = a.games if a.games is not None else min(int(g.run["eval_games"]) for g in gates.values())
    starts = min(len(ref.starts_m) for ref in refs.values())
    if not 1 <= n <= starts:
        return refuse(f"--games {n}: between 1 and the reference's {starts} starts")
    checks = {r: {s: suite_side(gates[r], s, n, a.device, refs[r]) for s in sides} for r in routes}
    ok = all(v["status"] == PASS for sd in checks.values() for c in sd.values() for v in c.values())
    res = {"what": "STE L4.2 scoring suite on known players (scripts/ste_l4_suite.py); observed in the training "
                   "simulator", "status_note": STATUS, "complete": True, "status": PASS if ok else FAIL,
           "games": n, "device": a.device, "gates_sha256": {r: g.sha256 for r, g in gates.items()},
           "reference_sha256": {r: g.reference["sha256"] for r, g in gates.items()}, "checks": checks}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "suite_check.md").write_text(render(res))
    (a.out / OUT_FILE).write_text(json.dumps(res, indent=1))           # written last
    print(f"scoring suite {res['status']}: {a.out / OUT_FILE}")
    return EXIT_DONE if ok else EXIT_CONTROL_FAILED


if __name__ == "__main__":
    sys.exit(main())
