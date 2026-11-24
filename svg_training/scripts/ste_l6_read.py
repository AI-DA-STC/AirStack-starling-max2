#!/usr/bin/env python
"""STE L3-L6 pipeline check, task L6.1: the per-route reads and the route comparison (spec
ste_learning/drafts/L3_L6_PIPELINE_SPEC.md section 3, fixed before any run). CPU, scoring files only: no training,
no game is played.

    ste_l6_read.py --manifest <read.toml> --out <folder>

The manifest names the run folders (absolute, or relative to svg_training/), each launched through
``scripts/ste_job.py`` (its ``exit_code`` file is how a stop is told from a crash)::

    suite_check = "<L4.2 folder>/suite_check.json"   # scripts/ste_l4_suite.py; required before the comparison
    held_arm = "<L4.1 folder>"                   # scripts/ste_l3_held_arm.py's --out (optional)
    [velocity]                                   # and [skills]
    pilot = "..."; run0 = "..."; guard = "..."; export_guard = "..."   # exports: scripts/ste_l6_export.py's --out
    strike = "..."; export_strike = "..."        # absent when the Strike run was not launched (run 0 FAIL, ...)
    poolonly_guard = "..."                       # L5.3 / L5.4 (optional); [skills] also poolonly_pilot (L5.4's own)

The words (section 3): per route PIPELINE WORKS / PIPELINE WORKS, RUN 0 FAILED / PIPELINE WORKS, RUN 0 INCONCLUSIVE /
PIPELINE DOES NOT WORK at <stage> (the first failing control, a non-finite stop, a crash, an export that does not
reload with its golden rows); ATTRIBUTION NOT READ at <stage>; HELD ARM NOT READ; COMPARISON NOT READ until the
scoring-suite check (L4.2) passes. The comparison, per side, on the same starts: the worst cell without the z_up_info
cells, the worst cells against each other, paired same-cell differences, the pooled row, each policy against the best
single fixed choice, the choice shares (skills). Every read is of "these two trained policies", INFO.

A state section 3 does not word (a stop at the cap or on request, a refused launch, a run short of its budget, a
missing required folder, a contradiction such as a Strike run after a failed run 0) is REFUSED (exit 2), never given
a new word. The export reload runs in a fresh process (``ste/export.py``'s reload check: onnxruntime and onnx's
reference evaluator); it does not settle the AirStack container's runtime.

Writes <out>/read.json and read.md. Exit codes: 0 done; 2 refused. Results are "observed in the training simulator";
pipeline check, not for flight."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

import numpy as np  # noqa: E402

from svg_training.ste import compare, exploit, jobs, pool, scoring, skills  # noqa: E402

EXIT_DONE, EXIT_REFUSED = 0, 2
EXIT_NONFINITE, EXIT_CONTROL_FAILED = 5, 6
UNWORDED_EXITS = {2: "refused to start", 3: "stopped at its cap", 4: "stopped on request"}
STATUS = "pipeline check, not for flight"
PASS = "PASS"
ROUTES = ("velocity", "skills")
SIDES = ("guard", "strike")
SIDE_NAME = {"guard": "Guard", "strike": "Strike"}
TASKS = {"velocity": {"pilot": "L3.2", "run0": "L3.4", "main": "L5.1", "poolonly": "L5.3"},
         "skills": {"pilot": "L3.3", "run0": "L3.5", "main": "L5.2", "poolonly": "L5.4"}}
EXPORT_TASK = "L6.2"
GATE_DIR = ROOT / "configs" / "ste_l3"
SCHEMAS = {"velocity": "ste-check-velocity-0", "skills": "ste-check-skills-0"}
Z_UP_LABEL = "vertical response not fitted in tier 1"     # spec section 3's label of the strike_high / strike_low cells
POOLED_TOL = 1e-9          # the pooled rate recomputed here against the run's own results.json (both exact means)
RELOAD_TIMEOUT_S = 600
POLICIES = "these two trained policies (one seed each; the intervals cover the sampling of the starts only)"
CANNOT_SHOW = [
    "one seed per route and side (no seed spread; the intervals are over the starts only)",
    "the 1.6 m tag only",
    "tier 1 training only (tier 2 only through the scripted smoke)",
    "no flight",
    "the estimate error off",
    "scripted opponents only (no self-play or league)",
    "no held-out opponent: every scored script was in the training pool, so adaptation to an unseen opponent is not "
    "tested",
    "the per-slot MLP and observation v0.1 of today (not the attention encoder or v0.3)",
    "a policy without memory or opponent identity (it can adapt only to what it observes)",
    "the skills route's closed-loop advantage (measured for the scripts by L4.1)",
    "a 550 M budget, not a budget of record"]


class Refused(Exception):
    """A state section 3 does not word, or folders that cannot be read together."""


# ---------------------------------------------------------------------------------------------------- the stages
def gates_of(name: str):
    return exploit.load_gates(GATE_DIR / f"{name}_gates.toml")


def path_of(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def need(m: dict, key: str, stage: str) -> Path:
    if key not in m:
        raise Refused(f"{stage}: the manifest names no folder ({key}); a required task not given is not worded")
    p = path_of(m[key])
    if not p.exists():
        raise Refused(f"{stage}: {p} does not exist")
    return p


def load_json(path: Path, stage: str) -> dict:
    if not path.is_file():
        raise Refused(f"{stage}: {path} is missing")
    return json.loads(path.read_text())


def controls_of(folder: Path) -> dict:
    p = folder / "controls.json"
    return json.loads(p.read_text()) if p.is_file() else {}


def first_not_pass(controls: dict) -> tuple[str, str] | None:
    return next(((k, v["status"]) for k, v in controls.items() if v.get("status") != PASS), None)


def stopped(folder: Path, stage: str) -> str | None:
    """Why the stage did not work (a failed control, a non-finite stop, a crash), None if it exited 0. A stop that
    section 3 does not word is refused."""
    p = folder / jobs.EXIT_FILE
    if not p.is_file():
        raise Refused(f"{stage}: {folder} holds no {jobs.EXIT_FILE} (not launched through scripts/ste_job.py, or "
                      f"still running)")
    code = int(p.read_text().strip())
    controls = controls_of(folder)
    if code == 0:
        bad = first_not_pass(controls)
        if bad:
            raise Refused(f"{stage}: exit 0 with control {bad[0]} {bad[1]} (inconsistent folder)")
        return None
    if code == EXIT_CONTROL_FAILED:
        bad = first_not_pass(controls)
        return f"control {bad[0]} {bad[1]} (exit 6)" if bad else "exit 6 (controls.json names no failing control)"
    if code == EXIT_NONFINITE:
        bad = first_not_pass(controls)
        return "a non-finite value (exit 5)" + (f", control {bad[0]} {bad[1]}" if bad else "")
    if code in UNWORDED_EXITS:
        raise Refused(f"{stage}: {UNWORDED_EXITS[code]} (exit {code}): section 3 has no word for it")
    return f"crashed (exit {code})"


def check_sha(got, gates, stage: str) -> None:
    if got != gates.sha256:
        raise Refused(f"{stage}: ran under gate sha256 {got}, the pre-registered gate file is {gates.sha256}")


# The fill step (spec section 2b, and the skills run 0 mark of the slice-2 addendum, 25 Nov 2026) writes these values
# AFTER the pilots, by design: a pilot ran under the gate file as it stood before the fill.
FILL_FIELDS = (("trainer", "side_overrides", "strike"), ("trainer", "game_steps_per_run"),
               ("run0", "skills_reach_min"))


def without_fill(doc: dict) -> dict:
    import copy
    doc = copy.deepcopy(doc)
    for *path, key in FILL_FIELDS:
        node = doc
        for part in path:
            node = node.get(part) if isinstance(node, dict) else None
        if isinstance(node, dict):
            node.pop(key, None)
    return doc


def check_pilot_sha(folder: Path, got, gates, stage: str) -> None:
    """A pilot ran under the pre-registered gate file, or under it as it stood before the fill step: its own copy
    (``<pilot>/gates.toml``, sha256 = the pilot's) equal to the gate file in every value but the fill fields."""
    if got == gates.sha256:
        return
    copy = folder / "gates.toml"
    if not copy.is_file() or exploit.sha256_file(copy) != got:
        raise Refused(f"{stage}: ran under gate sha256 {got}, the pre-registered gate file is {gates.sha256}, and "
                      f"the pilot's own copy {copy} is missing or is not that file")
    pre, now = tomllib.loads(copy.read_text()), tomllib.loads(Path(gates.path).read_text())
    if without_fill(pre) != without_fill(now):
        raise Refused(f"{stage}: ran under gate sha256 {got}, which differs from the pre-registered gate file "
                      f"{gates.sha256} in more than the fill step's fields {FILL_FIELDS}")


def read_pilot(folder: Path, gates, stage: str) -> str | None:
    why = stopped(folder, stage)
    if why:
        return why
    data = load_json(folder / "pilot.json", stage)
    if data.get("stopped") or not (folder / "pilot.md").is_file():
        raise Refused(f"{stage}: the pilot did not finish (stopped {data.get('stopped')!r}, pilot.md missing?)")
    check_pilot_sha(folder, data.get("gates_sha256"), gates, stage)
    controls = {k: v for side in data.get("eval", {}).get("per_side", {}).values()
                for k, v in side.get("controls", {}).items()}
    if not controls:
        raise Refused(f"{stage}: pilot.json records no controls")
    bad = first_not_pass(controls)                 # the pilot records its controls in pilot.json and exits 0
    return f"control {bad[0]} {bad[1]} (pilot.json)" if bad else None


def read_run0(folder: Path, gates, stage: str) -> tuple[str | None, str | None]:
    why = stopped(folder, stage)
    if why:
        return why, None
    data = load_json(folder / "learner_control.json", stage)
    if data.get("complete") is not True or data.get("status") not in ("PASS", "FAIL", "INCONCLUSIVE"):
        raise Refused(f"{stage}: learner_control.json is not complete or has no run 0 status")
    check_sha(data.get("gates_sha256"), gates, stage)
    return None, data["status"]


def opponents_of(gates, side: str) -> list:
    return list(gates.players["strikes" if side == "guard" else "guards"])


def read_main(folder: Path, gates, side: str, stage: str) -> tuple[str | None, dict | None]:
    """A trained run: results.json complete, trained to its budget, its INFO batch (the trained team against every
    script of the other team) as win indicators per cell."""
    why = stopped(folder, stage)
    if why:
        return why, None
    res = load_json(folder / "results.json", stage)
    if res.get("complete") is not True:
        raise Refused(f"{stage}: results.json is not complete")
    check_sha(res.get("gates_sha256"), gates, stage)
    if res.get("side") != side:
        raise Refused(f"{stage}: a {res.get('side')} run, expected {side}")
    if res.get("reference", {}).get("start_sha256") != gates.reference["start_sha256"]:
        raise Refused(f"{stage}: scored on starts {res.get('reference', {}).get('start_sha256')}, the gate file's "
                      f"reference starts are {gates.reference['start_sha256']}")
    if res.get("budget_reached") is not True:
        raise Refused(f"{stage}: trained short of its game-step budget ({res.get('train_stop')}): not worded")
    opps = opponents_of(gates, side)
    cell = (lambda o: f"{o} v {exploit.EXPLOITER}") if side == "strike" else (lambda o: f"{exploit.EXPLOITER} v {o}")
    if list(res.get("info", {})) != [cell(o) for o in opps]:
        raise Refused(f"{stage}: the INFO cells {list(res.get('info', {}))} are not the gate file's {opps}")
    if controls_of(folder).get("ctl_paired_starts_info", {}).get("status") != PASS:
        raise Refused(f"{stage}: no passing ctl_paired_starts_info (the INFO batch on the reference starts)")
    need_blocks = ["pooled", "best_single_choice"] if gates.pool["enabled"] else []
    need_blocks += ["choice_by_decision"] if gates.learner.skills else []
    missing = [k for k in need_blocks if k not in res]
    if missing:
        raise Refused(f"{stage}: results.json lacks {missing} (section 3: the final phase writes them)")
    n = int(res["eval_games"])
    z = np.load(folder / "eval_info.npz")
    wins = compare.wins_by_cell(z["outcome"], opps, n, side)
    members = pool.pool_members(gates.players, "strike" if side == "guard" else "guard")
    if "pooled" in res:                            # the run's own pooled rate, recomputed from its per-game file
        mine = float(compare.per_start_mean(wins, members).mean())
        if abs(mine - float(res["pooled"]["rate"])) > POOLED_TOL:
            raise Refused(f"{stage}: the pooled rate from eval_info.npz {mine} is not results.json's "
                          f"{res['pooled']['rate']}")
    return None, {"folder": str(folder), "results": res, "wins": wins, "opponents": opps, "n": n,
                  "members": members, "gates": gates}


def reload_in_a_fresh_process(folder: Path) -> dict:
    """``export.reload_check`` in a new Python process (CPU): its numbers, or {"ok": False, "error": why}."""
    code = ("import json, sys\n"
            "try:\n    from svg_training.ste import export\n    out = export.reload_check(sys.argv[1])\n"
            "except ImportError as err:\n    out = {'ok': False, 'environment': str(err)}\n"
            "except ValueError as err:\n    out = {'ok': False, 'error': str(err)}\n"
            "print(json.dumps(out))")
    path = os.pathsep.join(p for p in (str(ROOT / "source"), os.environ.get("PYTHONPATH", "")) if p)
    env = {**os.environ, "PYTHONPATH": path, "CUDA_VISIBLE_DEVICES": ""}
    r = subprocess.run([sys.executable, "-c", code, str(folder)], env=env, capture_output=True, text=True,
                       timeout=RELOAD_TIMEOUT_S)
    if r.returncode != 0:
        return {"ok": False, "error": f"the reload process exited {r.returncode}: {r.stderr[-500:]}"}
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return {"ok": False, "error": f"unparseable reload output: {r.stdout[-300:]!r}"}
    if "environment" in out:                       # the export extra is missing: the environment, not the export
        raise Refused(f"the reload check cannot run in this environment ({out['environment']}): install the "
                      f"export extra (onnx, onnxruntime)")
    return out


def read_export(folder: Path, route: str, side: str, gates, run: Path, stage: str) -> tuple[str | None, dict]:
    """An export folder of ``scripts/ste_l6_export.py`` (launched through ste_job.py): its exit, schema, team, gate
    sha, the source checkpoint's sha256 equal to ``run``'s agent_final.pt, then the reload in a fresh process."""
    why = stopped(folder, stage)
    if why:
        return why, {}
    meta = tomllib.loads(load_json_text(folder / "interface.toml", stage))
    if (meta.get("policy_schema"), meta.get("team"), meta.get("gates_sha256")) != (SCHEMAS[route], side, gates.sha256):
        raise Refused(f"{stage}: the export is {meta.get('policy_schema')} / {meta.get('team')} under gate sha256 "
                      f"{meta.get('gates_sha256')}, expected {SCHEMAS[route]} / {side} / {gates.sha256}")
    agent = Path(run) / "agent_final.pt"
    if not agent.is_file() or meta.get("source_checkpoint_sha256") != exploit.sha256_file(agent):
        raise Refused(f"{stage}: the export's source checkpoint sha256 {meta.get('source_checkpoint_sha256')} is not "
                      f"the run's {agent} ({exploit.sha256_file(agent) if agent.is_file() else 'missing'})")
    r = reload_in_a_fresh_process(folder)
    return (None if r.get("ok") else f"the reload check: {r.get('error')}"), r


def load_json_text(path: Path, stage: str) -> str:
    if not path.is_file():
        raise Refused(f"{stage}: {path} is missing")
    return path.read_text()


# ---------------------------------------------------------------------------------------------------- the words
def route_read(route: str, m: dict) -> dict:
    gates, t = gates_of(route), TASKS[route]
    out: dict = {"stages": {}, "runs": {}, "exports": {}}

    def does_not_work(stage: str, why: str) -> dict:
        out.update(word=f"PIPELINE DOES NOT WORK at {stage}", why=why, stage=stage)
        return out

    stage = f"{t['pilot']} {route} pilot"
    why = read_pilot(need(m, "pilot", stage), gates, stage)
    if why:
        return does_not_work(stage, why)
    stage = f"{t['run0']} {route} run 0"
    why, run0 = read_run0(need(m, "run0", stage), gates, stage)
    if why:
        return does_not_work(stage, why)
    out["run0"] = run0
    launched = "strike" in m
    if run0 == "PASS" and not launched:
        raise Refused(f"{route}: run 0 PASS and no Strike run given (a required task not given)")
    if run0 == "FAIL" and launched:
        raise Refused(f"{route}: a Strike run after run 0 FAIL (the Strike run is not launched): a contradiction")
    if run0 == "INCONCLUSIVE" and launched and route == "skills":
        raise Refused("skills: a Strike run after run 0 INCONCLUSIVE (never launched on this route): a contradiction")
    for side in ("guard", "strike") if launched else ("guard",):
        stage = f"{t['main']} {route} {SIDE_NAME[side]} run"
        why, run = read_main(need(m, side, stage), gates, side, stage)
        if why:
            return does_not_work(stage, why)
        out["runs"][side] = run
        stage = f"{EXPORT_TASK} {route} {SIDE_NAME[side]} export"
        why, rel = read_export(need(m, f"export_{side}", stage), route, side, gates, Path(run["folder"]), stage)
        if why:
            return does_not_work(stage, why)
        out["exports"][side] = rel
    word = {"PASS": "PIPELINE WORKS", "FAIL": "PIPELINE WORKS, RUN 0 FAILED",
            "INCONCLUSIVE": "PIPELINE WORKS, RUN 0 INCONCLUSIVE"}[run0]
    out.update(word=word, why="every required task as section 3 lists it" if run0 == "PASS" else
               ("run 0 read FAIL at the full budget: the Strike run is not launched" if run0 == "FAIL" else
                "run 0 stopped at its cap reserve: " + ("the Strike run launched on the lead's recorded decision"
                                                         if launched else "no Strike run")))
    return out


def attribution(route: str, m: dict, rr: dict) -> dict:
    if "poolonly_guard" not in m:
        return {"word": "not given"}
    t = TASKS[route]
    if "guard" not in rr["runs"]:
        return {"word": f"ATTRIBUTION NOT READ at {rr['stage']}", "why": rr["why"]}
    po_gates = gates_of(f"{route}_poolonly")
    if route == "skills":
        stage = f"{t['poolonly']} skills pool-only pilot"
        why = read_pilot(need(m, "poolonly_pilot", stage), po_gates, stage)
        if why:
            return {"word": f"ATTRIBUTION NOT READ at {stage}", "why": why}
    stage = f"{t['poolonly']} {route} pool-only Guard run"
    why, po = read_main(need(m, "poolonly_guard", stage), po_gates, "guard", stage)
    if why:
        return {"word": f"ATTRIBUTION NOT READ at {stage}", "why": why}
    main = rr["runs"]["guard"]
    same_starts(main, po, f"{route} attribution")
    return {"word": "read", "label": "INFO", "what": f"pool + mask minus pool only, Guard side, {POLICIES}",
            "paired_cells": [{"opponent": o, **compare.paired_difference(main["wins"][o], po["wins"][o])}
                             for o in main["opponents"]],
            "pooled_difference": compare.paired_difference(compare.per_start_mean(main["wins"], main["members"]),
                                                           compare.per_start_mean(po["wins"], po["members"]))}


def held_arm(m: dict) -> dict:
    if "held_arm" not in m:
        return {"word": "not given"}
    folder = path_of(m["held_arm"])
    p = folder / jobs.EXIT_FILE
    if not p.is_file():
        raise Refused(f"L4.1 held-command arm: {folder} holds no {jobs.EXIT_FILE} (launch it through ste_job.py)")
    code = int(p.read_text().strip())
    if code not in (EXIT_DONE, EXIT_CONTROL_FAILED):
        raise Refused(f"L4.1 held-command arm: exit {code}: section 3 has no word for it")
    bad = first_not_pass(controls_of(folder))
    if (code == EXIT_CONTROL_FAILED) != bool(bad):
        raise Refused(f"L4.1 held-command arm: exit {code} with controls {bad or 'all PASS'} (inconsistent folder)")
    if bad:
        return {"word": "HELD ARM NOT READ", "why": f"control {bad[0]} {bad[1]} (hold 1 is not the reference)"}
    res = load_json(folder / "results.json", "L4.1 held-command arm")
    if res.get("complete") is not True:
        raise Refused("L4.1 held-command arm: results.json is not complete")
    return {"word": "read", "label": "INFO", "results": str(folder / "results.json"),
            "what": "per script and opponent, the held against the closed-loop wins (scripts/ste_l3_held_arm.py)"}


def same_starts(a: dict, b: dict, what: str) -> None:
    ra, rb = a["results"], b["results"]
    for key in ("eval_games", "reference", "game_file"):
        if ra.get(key) != rb.get(key):
            raise Refused(f"{what}: {key} differs ({ra.get(key)} against {rb.get(key)}): not the same starts and game")
    if a["opponents"] != b["opponents"] or a["gates"].players != b["gates"].players:
        raise Refused(f"{what}: the [players] of the two gate files differ")


def best_single(run: dict, side: str) -> dict:
    gates, n, members = run["gates"], run["n"], run["members"]
    ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
    variant = exploit.ref_variant(gates, "base")
    choices = skills.team_skills(gates.players, side)
    bsc = scoring.best_single_choice(ref, variant, side, choices, members, n)
    won = exploit.STRIKE_WIN if side == "strike" else exploit.GUARD_WIN
    wins = {o: np.asarray(ref.cell(variant, *((o, bsc["best"]) if side == "strike" else (bsc["best"], o)))["outcome"]
                          [:n]) == won for o in members}
    return {"best": bsc["best"], "rate": bsc["per_choice"][bsc["best"]]["rate"],
            "per_choice_rate": {s: v["rate"] for s, v in bsc["per_choice"].items()}, "source": bsc["source"],
            "y": compare.per_start_mean(wins, members)}


def compare_side(side: str, rr: dict) -> dict:
    missing = [r for r in ROUTES if side not in rr[r]["runs"]]
    if missing:
        return {"compared": False,
                "why": "; ".join(f"the {r} {SIDE_NAME[side]} run is not read ({rr[r]['word']})" for r in missing)}
    v, s = rr["velocity"]["runs"][side], rr["skills"]["runs"][side]
    same_starts(v, s, f"{side} comparison")
    z_up = list(v["gates"].players["z_up_info"])
    best = best_single(v, side)
    policies = {}
    for route, run in (("velocity", v), ("skills", s)):
        y = compare.per_start_mean(run["wins"], run["members"])
        p = {"headline": labelled(compare.headline(run["wins"], z_up)), "pooled": scoring.pooled_row(
            {o: run["wins"][o] for o in run["members"]}),
             "against_best_single_choice": {"best": best["best"], **compare.paired_difference(y, best["y"])}}
        if route == "skills" and "choice_by_decision" in run["results"]:
            p["choice_share"] = {o: {"overall": compare.overall_share(e), "by_decision": e}
                                 for o, e in run["results"]["choice_by_decision"].items()}
            p["choice_share_note"] = ("described, not worded; the late decision bins are survivor-biased; a share that "
                                      "changes with the opponent on the same starts is the only sign of adaptation "
                                      "this check can give")
        policies[route] = p
    wv, ws = policies["velocity"]["headline"]["worst"], policies["skills"]["headline"]["worst"]
    order = list(dict.fromkeys([wv["opponent"], ws["opponent"], *v["opponents"]]))
    yv, ys = compare.per_start_mean(v["wins"], v["members"]), compare.per_start_mean(s["wins"], s["members"])
    trivial = sorted(set(policies["velocity"]["pooled"]["trivial_cells"]) | set(policies["skills"]["pooled"]
                                                                                 ["trivial_cells"]))
    return {"compared": True, "what": f"velocity minus skills, {SIDE_NAME[side]} team, {POLICIES}",
            "k": len(v["opponents"]), "games": v["n"], "policies": policies,
            "worst_cells": {"velocity": wv, "skills": ws, "word": compare.intervals_word(wv["ci"], ws["ci"]),
                            "rule": "velocity's worst cell against skills' worst cell: above / below when the Wilson "
                                    "intervals are disjoint, else not distinguishable"},
            "paired_cells": [{"opponent": o, "z_up_info": o in z_up, **({"label": Z_UP_LABEL} if o in z_up else {}),
                              **compare.paired_difference(v["wins"][o], s["wins"][o])} for o in order],
            "pooled_difference": {**compare.paired_difference(yv, ys), "trivial_cells": trivial,
                                  "flag": "trivial cells (rate 0 or 1) pull the mean" if trivial else ""},
            "best_single_choice": {k: best[k] for k in ("best", "rate", "per_choice_rate", "source")}}


def labelled(head: dict) -> dict:
    """The spec's label on each z_up_info cell beside the headline."""
    head["z_up_info_cells"] = {o: {**c, "label": Z_UP_LABEL} for o, c in head["z_up_info_cells"].items()}
    return head


def comparison(m: dict, rr: dict) -> dict:
    if "suite_check" not in m:
        return {"word": "COMPARISON NOT READ", "why": "the scoring-suite check (L4.2) is not given; it is required "
                                                      "before the comparison is written"}
    suite_path = path_of(m["suite_check"])
    suite = load_json(suite_path, "L4.2 scoring-suite check")
    code_file = suite_path.parent / jobs.EXIT_FILE
    if not code_file.is_file():
        raise Refused(f"L4.2 scoring-suite check: {suite_path.parent} holds no {jobs.EXIT_FILE} (launch it through "
                      f"ste_job.py)")
    code = int(code_file.read_text().strip())
    if (code, suite.get("status")) not in ((EXIT_DONE, PASS), (EXIT_CONTROL_FAILED, "FAIL")):
        raise Refused(f"L4.2 scoring-suite check: exit {code} with status {suite.get('status')} (0 with PASS, 6 with "
                      f"FAIL)")
    missing = [f"{r} {s}" for r in ROUTES for s in SIDES if s not in suite.get("checks", {}).get(r, {})]
    if missing:
        raise Refused(f"L4.2 scoring-suite check: a partial suite, no entry for {missing}")
    want = {r: gates_of(r).sha256 for r in ROUTES}
    if suite.get("gates_sha256") != want:
        raise Refused(f"L4.2 scoring-suite check: ran on gate files {suite.get('gates_sha256')}, not {want}")
    games = min(int(gates_of(r).run["eval_games"]) for r in ROUTES)
    if int(suite.get("games", 0)) < games:
        raise Refused(f"L4.2 scoring-suite check: {suite.get('games')} games, the comparison's {games} starts need "
                      f"at least as many")
    if suite.get("complete") is not True or suite.get("status") != PASS:   # scripts/ste_l4_suite.py's file
        return {"word": "COMPARISON NOT READ", "why": f"the scoring-suite check (L4.2) reads {suite.get('status')}"}
    return {"word": "read", "label": "INFO", **{side: compare_side(side, rr) for side in SIDES}}


# ---------------------------------------------------------------------------------------------------- output
def plain(obj):
    if isinstance(obj, dict):
        return {k: plain(v) for k, v in obj.items() if k not in ("wins", "gates", "y")}
    if isinstance(obj, (list, tuple)):
        return [plain(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def render(out: dict) -> str:
    lines = [f"Simulator: tier 1 training simulator; {STATUS}. Observed in the training simulator. Label: INFO. "
             f"{out['review']}", "", f"Every read is of {POLICIES}.", "", "## Per route", "",
             "| Route | Word | Why |", "|---|---|---|"]
    lines += [f"| {r} | **{v['word']}** | {v['why']} |" for r, v in out["routes"].items()]
    lines += ["", "## Separate reads", ""]
    for r, a in out["attribution"].items():
        line = f"- Attribution, {r}: **{a['word']}**" + (f" ({a['why']})" if a.get("why") else "")
        if "pooled_difference" in a:
            d = a["pooled_difference"]
            line += (f"; pooled row, pool + mask minus pool only: {d['diff']:+.3f} [{d['ci'][0]:+.3f}, "
                     f"{d['ci'][1]:+.3f}], {d['word']} (cells in read.json)")
        lines.append(line)
    lines += [f"- Held-command arm: **{out['held_arm']['word']}**" +
              (f" ({out['held_arm']['why']})" if out["held_arm"].get("why") else ""), ""]
    c = out["comparison"]
    lines += ["## Comparison (INFO)", "", f"**{c['word']}**" + (f": {c['why']}" if c.get("why") else ""), ""]
    for side in SIDES:
        if side not in c:
            continue
        sc = c[side]
        lines += [f"### {SIDE_NAME[side]} team", ""]
        if not sc["compared"]:
            lines += [f"Not compared: {sc['why']}", ""]
            continue
        lines += [f"{sc['what']}; K = {sc['k']} opponent cells, {sc['games']} starts.", "",
                  "| Policy | Worst cell (not z_up_info) | Rate [95 %] | Pooled row [95 %] | Against the best single "
                  "choice |", "|---|---|---|---|---|"]
        for r, p in sc["policies"].items():
            w, po, b = p["headline"]["worst"], p["pooled"], p["against_best_single_choice"]
            lines.append(f"| {r} | {w['opponent']} | {w['rate']:.3f} [{w['ci'][0]:.3f}, {w['ci'][1]:.3f}] | "
                         f"{po['rate']:.3f} [{po['ci'][0]:.3f}, {po['ci'][1]:.3f}] | {b['diff']:+.3f} "
                         f"[{b['ci'][0]:+.3f}, {b['ci'][1]:+.3f}] v {b['best']}: {b['word']} |")
        lines += ["", f"Worst cells, velocity against skills: **{sc['worst_cells']['word']}**.", "",
                  "| Opponent | velocity minus skills, paired [95 %] | Word |", "|---|---|---|"]
        for d in sc["paired_cells"]:
            tag = f" ({Z_UP_LABEL})" if d["z_up_info"] else ""
            lines.append(f"| {d['opponent']}{tag} | {d['diff']:+.3f} [{d['ci'][0]:+.3f}, {d['ci'][1]:+.3f}] | "
                         f"{d['word']} |")
        pd = sc["pooled_difference"]
        lines += ["", f"Pooled row, velocity minus skills: {pd['diff']:+.3f} [{pd['ci'][0]:+.3f}, {pd['ci'][1]:+.3f}]"
                  f", **{pd['word']}**" + (f"; {pd['flag']}: {', '.join(pd['trivial_cells'])}" if pd["flag"] else ""),
                  ""]
        share = sc["policies"]["skills"].get("choice_share")
        if share:
            lines += ["Choice share of the skills policy over all decisions, per opponent (described, not worded; by "
                      "decision index in read.json):", ""]
            lines += [f"- {o}: " + ", ".join(f"{k} {v:.2f}" if v is not None else f"{k} -" for k, v in
                                             e["overall"].items()) for o, e in share.items()]
            lines.append("")
    lines += ["## What it cannot show", ""] + [f"- {x}" for x in out["cannot_show"]]
    lines += ["", out["added_reads"], ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ste_l6_read.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        if (a.out / "read.json").exists():
            raise Refused(f"{a.out} already holds read.json: a new read needs a new folder")
        m = tomllib.loads(a.manifest.read_text())
        for route in ROUTES:
            if route not in m:
                raise Refused(f"the manifest has no [{route}] table")
        rr = {route: route_read(route, m[route]) for route in ROUTES}
        out = {"what": "STE L6.1 per-route reads and route comparison (scripts/ste_l6_read.py); observed in the "
                       "training simulator",
               "status": STATUS, "label": "INFO", "policies": POLICIES,
               "review": "Draft until two independent reviewers have checked it (R22).",
               "manifest": str(a.manifest), "manifest_sha256": exploit.sha256_file(a.manifest),
               "gates_sha256": {name: gates_of(name).sha256 for name in
                                ("velocity", "skills", "velocity_poolonly", "skills_poolonly")},
               "routes": {r: {k: v for k, v in rr[r].items() if k in ("word", "why", "stage", "run0", "exports")}
                          for r in ROUTES},
               "attribution": {r: attribution(r, m[r], rr[r]) for r in ROUTES},
               "held_arm": held_arm(m),
               "comparison": comparison(m, rr),
               "cannot_show": CANNOT_SHOW,
               "added_reads": "A second seed or any other read paid from the unallocated hours is labelled an added "
                              "read; it never replaces a pre-registered one.",
               "export_runtime_note": "the reload check (onnxruntime and onnx's reference evaluator) does not settle "
                                      "whether onnxruntime or torch runs in the AirStack ground container"}
    except Refused as err:
        print(f"refused: {err}", file=sys.stderr)
        return EXIT_REFUSED
    out = plain(out)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "read.json").write_text(json.dumps(out, indent=1, allow_nan=False))
    (a.out / "read.md").write_text(render(out))
    for r in ROUTES:
        print(f"{r}: {out['routes'][r]['word']}")
    return EXIT_DONE


if __name__ == "__main__":
    sys.exit(main())
