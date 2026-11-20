#!/usr/bin/env python
"""L0.14 Crazyflie route check, part 2 (STE learning track; PLAN.md section 4): which team sizes fit which arena at the
Starling's 1.10 m filter distance, from the Crazyflie repository's offline planner (``plan_guard``). INFO, no gate.
Simulated matches on the planner's stand-in aircraft (a first-order lag); nothing here is a flight result.

    cd <svg_training>
    python3 scripts/ste_l014_arena_fit.py --run-dir runs/<date>_ste_l014/arena_fit \\
        --work-dir /tmp/claude-1000/<...>/scratchpad/l014_planner [--cases 5v3] [--matches 3]

The Crazyflie repository (``[arena_fit] cf_repo``) is another repository and is only READ: its planner package and its
``arena.yaml`` are copied into ``--work-dir`` (refused if that folder is inside the repository), and every planner
process imports the copy with ``PYTHONDONTWRITEBYTECODE=1`` and ``CRAZYSWARM_ARENA`` pointing at an arena file in the work
folder. The repository's commit and ``git status`` are recorded before and after; a change fails the run (exit 6).

Cases (settings: ``configs/ste_l014.toml [arena_fit]``):
- every team size of ``sizes`` in every arena of ``arenas``, the planner's default pairing (``pairing``), seeds
  ``seed0 .. seed0 + matches - 1`` (the planner's own seed numbering), lag ``tau_s``;
- ``lag_check``: the 20 Nov repeat at the Starling's lag;
- in ``matrix_arenas``: every built-in defence against every built-in attack, ``matrix_seeds`` seeds each, every size;
- follow-up (``followup_*``, added after the sweep): one change at a time, the after-match finale flown, or the planner's
  own strike radius (``--kind followup`` runs only these).
Rules: the planner's ``rules`` set with its strike radius set to ``strike_radius_m`` (the STE zone radius).
Arenas: ``room`` = the Crazyflie room as surveyed (the repository's arena.yaml polygon); ``circle_3_25`` = the same room
with the planner's own ``arena_radius`` set to half the square side (a circle round the room centre); ``square_6_5`` = a
square polygon of side ``square_side_m`` round the room centre (an arena.yaml written in the work folder).
The planner's own floor marks are refused at 1.10 m in the small arenas, so every case uses the same hand-set marks
(:func:`hand_marks`), round the protected point placed at the room centre.

Per case, one JSON in ``<run-dir>/cases/``; then ``<run-dir>/arena.json``: provenance, settings, marks, and per case the
matches, defence wins, matches with at least one solver-emergency tick (counted apart from every other safety failure),
the closest airborne pair in metres and how many matches came closer than the 1.10 m filter distance.

This file runs under the planner's interpreter (``[arena_fit] python``: numpy, scipy, pyyaml) as well as the training
environment (tests): standard library, numpy and pyyaml only, no import of svg_training."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "ste_l014.toml"
EXIT_OK, EXIT_REFUSED, EXIT_CONTROL_FAILED = 0, 2, 6


# ------------------------------------------------------------------------------------------------ pure helpers
def hand_marks(defenders: int, attackers: int, r_def_m: float, r_att_m: float, centre_xy, bearing0_deg: float) -> dict:
    """Floor marks {name: [x, y, 0.0]}: defenders D1.. evenly on a ring of r_def_m round centre_xy, D1 at bearing0_deg;
    attackers A1.. on a ring of r_att_m, each half-way between two neighbouring defender bearings, in the gaps after D1, D2,
    ... (so the attack starts on one side). Refuses (ValueError) more attackers than gaps."""
    if defenders < 1 or attackers < 1 or attackers > defenders:
        raise ValueError(f"{defenders} defenders leave {defenders} gaps; {attackers} attackers do not fit")
    cx, cy = float(centre_xy[0]), float(centre_xy[1])
    b0, step = math.radians(bearing0_deg), 2.0 * math.pi / defenders
    marks = {}
    for i in range(defenders):
        b = b0 + i * step
        marks[f"D{i + 1}"] = [cx + r_def_m * math.cos(b), cy + r_def_m * math.sin(b), 0.0]
    for j in range(attackers):
        b = b0 + (j + 0.5) * step
        marks[f"A{j + 1}"] = [cx + r_att_m * math.cos(b), cy + r_att_m * math.sin(b), 0.0]
    return marks


def square_arena(arena_yaml_text: str, side_m: float) -> str:
    """The arena.yaml text with its room replaced by a square of side_m round the file's own centre (counter-clockwise),
    radius_tested and ceiling_pinch_radius = side_m / 2 (the circle inside it), radius_lost = that + 0.30 m (the file's
    own convention). Every other key is kept."""
    import yaml
    d = yaml.safe_load(arena_yaml_text)
    a = d["arena"]
    cx, cy = (float(v) for v in a["centre"])
    h = side_m / 2.0
    a["polygon"] = [[cx + h, cy - h], [cx + h, cy + h], [cx - h, cy + h], [cx - h, cy - h]]
    a["radius_tested"] = h
    a["ceiling_pinch_radius"] = h
    a["radius_lost"] = h + 0.30
    head = (f"# L0.14 (svg_training): the Crazyflie room's arena.yaml with the room replaced by a {side_m} m square round\n"
            "# its centre. Written into a scratch folder; never into the Crazyflie repository.\n")
    return head + yaml.safe_dump(d, sort_keys=False)


def check_work_dir(cf_repo: Path, work_dir: Path) -> None:
    """Refuse (ValueError) a work folder inside (or equal to) the Crazyflie repository."""
    repo, work = Path(cf_repo).expanduser().resolve(), Path(work_dir).expanduser().resolve()
    if work == repo or repo in work.parents:
        raise ValueError(f"the work folder {work} is inside the Crazyflie repository {repo}: nothing may be written there")


def summarise_case(rows: list[dict], d_cc_m: float) -> dict:
    """Matches, defence wins, matches with at least one solver-emergency tick (and the ticks), matches with any OTHER safety
    failure, the closest airborne pair (m) and the matches whose closest pair came inside d_cc_m."""
    other = [r for r in rows if any(not f.startswith("solver emergency") for f in r["failures"])]
    seps = [r["sep_m"] for r in rows if math.isfinite(r["sep_m"])]
    return {"matches": len(rows), "defence_wins": sum(r["winner"] == "defense" for r in rows),
            "emergency_matches": sum(r["emergency"] > 0 for r in rows), "emergency_ticks": sum(r["emergency"] for r in rows),
            "other_failure_matches": len(other), "closest_pair_m": min(seps) if seps else None,
            "matches_closer_than_d_cc": sum(r["sep_m"] < d_cc_m for r in rows),
            "mean_match_s": (sum(r["t_s"] for r in rows) / len(rows)) if rows and all("t_s" in r for r in rows) else None}


def load_settings(path: Path = CONFIG) -> dict:
    return tomllib.loads(Path(path).read_text())["arena_fit"]


def tree_sha256(folder: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(q for q in Path(folder).rglob("*") if q.is_file() and "__pycache__" not in q.parts):
        h.update(str(p.relative_to(folder)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True).stdout.strip()


# ------------------------------------------------------------------------------------------------ the copy
def prepare(cfg: dict, work_dir: Path) -> dict:
    """Copy the planner package and arena.yaml into work_dir (outside the repository), write the square arena; return the
    provenance: paths, commit, status, sha256 of the copied package, interpreter versions."""
    repo = Path(cfg["cf_repo"]).expanduser().resolve()
    work = Path(work_dir).expanduser().resolve()
    check_work_dir(repo, work)
    copy = work / "cf_copy"
    if copy.exists():
        shutil.rmtree(copy)
    pkg = repo / cfg["package"]
    shutil.copytree(pkg, copy / pkg.name, ignore=shutil.ignore_patterns("__pycache__"))
    room_text = (repo / cfg["arena_yaml"]).read_text()
    (work / "arena_room.yaml").write_text(room_text)
    (work / "arena_square.yaml").write_text(square_arena(room_text, float(cfg["square_side_m"])))
    vers = subprocess.run([cfg["python"], "-c", "import sys, numpy, scipy, yaml; print(sys.version.split()[0], numpy.__version__, "
                           "scipy.__version__, yaml.__version__)"], capture_output=True, text=True).stdout.split()
    return {"repo": str(repo), "commit": _git(repo, "rev-parse", "HEAD"),
            "status_porcelain": _git(repo, "status", "--porcelain", "--ignored"), "package": cfg["package"],
            "package_sha256": tree_sha256(copy / pkg.name), "copy_dir": str(copy), "work_dir": str(work),
            "arena_files": {"room": str(work / "arena_room.yaml"), "square": str(work / "arena_square.yaml")},
            "arena_room_sha256": hashlib.sha256(room_text.encode()).hexdigest(),
            "python": cfg["python"], "versions": dict(zip(("python", "numpy", "scipy", "pyyaml"), vers))}


def guard_settings(cfg: dict, arena: str) -> dict:
    """GuardConfig fields changed from the planner's defaults for one arena."""
    s = {"d_cc": cfg["d_cc_m"], "cc_z_ratio": cfg["cc_z_ratio"], "v_max_defense": cfg["v_max_defense_mps"],
         "v_max_attack": cfg["v_max_attack_mps"], "floor": cfg["floor_m"], "ceiling": cfg["ceiling_m"]}
    if arena == "circle_3_25":
        s["arena_radius"] = float(cfg["square_side_m"]) / 2.0
    return s


def arena_file(prov: dict, arena: str) -> str:
    return prov["arena_files"]["square" if arena == "square_6_5" else "room"]


def run_case(cfg: dict, prov: dict, case: dict, out_dir: Path) -> Path:
    """One case in a planner process (the copy, the case's arena file); returns its JSON path. Raises on a child failure."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = {**case, "settings": guard_settings(cfg, case["arena"]), "rules": cfg["rules"],
            "rule_params": {"strike_radius": case.get("strike_radius_m", cfg["strike_radius_m"])}, "vip_z_m": cfg["vip_z_m"],
            "defender_ring_m": cfg["defender_ring_m"], "attacker_ring_m": cfg["attacker_ring_m"],
            "bearing0_deg": cfg["bearing0_deg"], "copy_dir": prov["copy_dir"], "out": str(out_dir / f"{case['name']}.json")}
    spec_path = out_dir / f"{case['name']}.spec.json"
    spec_path.write_text(json.dumps(spec, indent=1))
    env = {**os.environ, "CRAZYSWARM_ARENA": arena_file(prov, case["arena"]), "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONPATH": prov["copy_dir"], "OMP_NUM_THREADS": str(cfg["threads"]), "MKL_NUM_THREADS": str(cfg["threads"]),
           "OPENBLAS_NUM_THREADS": str(cfg["threads"])}
    p = subprocess.run([cfg["python"], "-B", str(Path(__file__).resolve()), "--child", str(spec_path)], env=env,
                       capture_output=True, text=True, cwd=prov["work_dir"])
    if p.returncode != 0:
        raise RuntimeError(f"case {case['name']} failed (exit {p.returncode}):\n{p.stderr[-3000:]}")
    return Path(spec["out"])


def child(spec_path: str) -> int:
    """Inside a planner process: import the copy, check the marks, play the case's matches, write the case JSON."""
    import dataclasses

    import numpy as np
    spec = json.loads(Path(spec_path).read_text())
    sys.path.insert(0, spec["copy_dir"])
    from crazyflie_shows import escort, safety
    from crazyflie_shows import plan_guard as pg
    from crazyflie_shows.guard import policies
    from crazyflie_shows.guard import rules as rule_sets
    from crazyflie_shows.guard.config import GuardConfig, override, problems
    from crazyflie_shows.guard.world import ATTACK, DEFENSE
    safety.require_measured_arena("L0.14 arena fit")
    if not Path(safety.ARENA_FILE).resolve().is_relative_to(Path(os.environ["CRAZYSWARM_ARENA"]).resolve().parent):
        raise SystemExit(f"the planner read {safety.ARENA_FILE}, not the work folder's arena file")
    cfg = override(GuardConfig(), dict(spec["settings"]))
    rules = rule_sets.make(spec["rules"], dict(spec["rule_params"]))
    vip = np.array([*cfg.room_center, spec["vip_z_m"]], float)
    marks = hand_marks(spec["defenders"], spec["attackers"], spec["defender_ring_m"], spec["attacker_ring_m"],
                       cfg.room_center, spec["bearing0_deg"])
    D = [k for k in marks if k.startswith("D")]
    A = [k for k in marks if k.startswith("A")]
    refused = list(problems(cfg)) + list(rules.problems(cfg))
    bad_marks, starts = pg.mark_problems(cfg, rules, vip, {k: np.array(v, float) for k, v in marks.items()}, D, A)
    refused += bad_marks
    finale = bool(spec.get("finale", False))
    if finale:
        from crazyflie_shows.guard import finale as finale_mod
        refused += list(finale_mod.check(cfg, {}))
    pairings = ([(d, a) for d in policies.available(DEFENSE) for a in policies.available(ATTACK)]
                if spec["pairings"] == "all" else [tuple(p) for p in spec["pairings"]])
    rows = []
    t0 = time.time()
    if not refused:
        for d, a in pairings:
            for s in spec["seeds"]:
                res, met, _ = pg.simulate(cfg, rules, d, a, starts, D, A, vip, int(s), None, None, float(spec["tau_s"]), 0.0,
                                          finale=finale)
                rows.append({"defense": d, "attack": a, "seed": int(s), "winner": res.winner, "t_s": float(res.t),
                             "strikes": int(res.strikes), "downs": int(res.downs), "sep_m": float(met["sep"]),
                             "sep_pair": met["sep_pair"], "floor_ratio": float(met["floor"]), "room_m": float(met["room"]),
                             "emergency": int(met["emergency"]), "backstop": int(met["backstop"]),
                             "not_converged": int(met.get("not_converged", 0)), "corrected": int(met.get("corrected", 0)),
                             "finale": met.get("finale", ""), "failures": pg.safety_failures(cfg, met)})
    out = {"name": spec["name"], "defenders": spec["defenders"], "attackers": spec["attackers"], "arena": spec["arena"],
           "tau_s": spec["tau_s"], "kind": spec["kind"], "finale": finale, "seeds": spec["seeds"], "pairings": [list(p) for p in pairings],
           "settings": {k: getattr(cfg, k) for k in spec["settings"]}, "guard_config": {
               k: (list(v) if isinstance(v, tuple) else v) for k, v in dataclasses.asdict(cfg).items()},
           "rules": {"name": spec["rules"], **rules.p}, "room": escort.describe_room(cfg), "arena_file": safety.ARENA_FILE,
           "vip": vip.tolist(), "marks": marks, "refused": refused, "rows": rows, "seconds": time.time() - t0}
    Path(spec["out"]).write_text(json.dumps(out, indent=1))
    return 0


# ------------------------------------------------------------------------------------------------ the run
def cases(cfg: dict) -> list[dict]:
    seeds = list(range(int(cfg["seed0"]), int(cfg["seed0"]) + int(cfg["matches"])))
    out = []
    for arena in cfg["arenas"]:
        for g, s in cfg["sizes"]:
            out.append({"name": f"{g}v{s}_{arena}_tau{cfg['tau_s']}", "defenders": g, "attackers": s, "arena": arena,
                        "tau_s": cfg["tau_s"], "kind": "pairing", "pairings": [cfg["pairing"]], "seeds": seeds})
    for g, s, arena, tau in cfg["lag_check"]:
        out.append({"name": f"{g}v{s}_{arena}_tau{tau}", "defenders": g, "attackers": s, "arena": arena, "tau_s": tau,
                    "kind": "lag_check", "pairings": [cfg["pairing"]], "seeds": seeds})
    mseeds = list(range(int(cfg["seed0"]), int(cfg["seed0"]) + int(cfg["matrix_seeds"])))
    for arena in cfg["matrix_arenas"]:
        for g, s in cfg["sizes"]:
            out.append({"name": f"{g}v{s}_{arena}_tau{cfg['tau_s']}_matrix", "defenders": g, "attackers": s, "arena": arena,
                        "tau_s": cfg["tau_s"], "kind": "matrix", "pairings": "all", "seeds": mseeds})
    for variant in cfg.get("followup_variants", []):
        for arena in cfg["followup_arenas"]:
            for g, s in cfg["followup_sizes"]:
                c = {"defenders": g, "attackers": s, "arena": arena, "tau_s": cfg["tau_s"], "kind": f"followup_{variant}",
                     "pairings": [cfg["pairing"]], "seeds": seeds}
                if variant == "finale":
                    c.update(name=f"{g}v{s}_{arena}_tau{cfg['tau_s']}_finale", finale=True)
                elif variant == "planner_strike_radius":
                    r = cfg["planner_strike_radius_m"]
                    c.update(name=f"{g}v{s}_{arena}_tau{cfg['tau_s']}_strike{r}", strike_radius_m=r)
                else:
                    raise ValueError(f"unknown follow-up variant {variant!r}")
                out.append(c)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run-dir", help="output folder under runs/")
    ap.add_argument("--work-dir", help="scratch folder OUTSIDE the Crazyflie repository for the planner copy")
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--cases", default="", help="only cases whose name contains this text (smoke)")
    ap.add_argument("--kind", default="", help="only cases of this kind (pairing, lag_check, matrix, followup_...)")
    ap.add_argument("--matches", type=int, default=None, help="override seeds per case (smoke; stamped in arena.json)")
    ap.add_argument("--child", default=None, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a.child:
        return child(a.child)
    if not a.run_dir or not a.work_dir:
        ap.error("--run-dir and --work-dir are required")
    run = Path(a.run_dir).resolve()
    if (ROOT / "runs").resolve() not in run.parents:
        print(f"refusing: {run} is not under {ROOT / 'runs'}", file=sys.stderr)
        return EXIT_REFUSED
    if (run / "arena.json").exists():
        print(f"refusing: {run / 'arena.json'} exists (one run per folder)", file=sys.stderr)
        return EXIT_REFUSED
    cfg = load_settings(Path(a.config))
    try:
        prov = prepare(cfg, Path(a.work_dir))
    except ValueError as e:
        print(f"refusing: {e}", file=sys.stderr)
        return EXIT_REFUSED
    todo = [c for c in cases(cfg) if a.cases in c["name"] and (not a.kind or c["kind"].startswith(a.kind))]
    if a.matches is not None:
        todo = [{**c, "seeds": c["seeds"][:a.matches]} for c in todo]
    print(f"{len(todo)} cases, {sum(len(c['seeds']) for c in todo)} seed runs; planner copy of {prov['commit'][:7]} in "
          f"{prov['work_dir']}", flush=True)
    t0 = time.time()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(cfg["parallel"])) as pool:
        futs = {pool.submit(run_case, cfg, prov, c, run / "cases"): c for c in todo}
        for f in concurrent.futures.as_completed(futs):
            data = json.loads(f.result().read_text())
            s = summarise_case(data["rows"], cfg["d_cc_m"]) if data["rows"] else None
            results.append({k: data[k] for k in ("name", "defenders", "attackers", "arena", "tau_s", "kind", "finale", "refused",
                                                 "room", "marks", "vip", "settings", "rules")} | {"summary": s})
            print(f"[{data['name']}] " + ("REFUSED: " + "; ".join(data["refused"]) if data["refused"] else
                  f"{s['matches']} matches, defence won {s['defence_wins']}, emergency in {s['emergency_matches']} "
                  f"({s['emergency_ticks']} ticks), other failures {s['other_failure_matches']}, closest pair "
                  f"{s['closest_pair_m']:.2f} m ({data['seconds']:.0f} s)"), flush=True)
    order = [c["name"] for c in todo]
    results.sort(key=lambda r: order.index(r["name"]))
    after = _git(Path(prov["repo"]), "status", "--porcelain", "--ignored")
    commit_after = _git(Path(prov["repo"]), "rev-parse", "HEAD")
    untouched = after == prov["status_porcelain"] and commit_after == prov["commit"]
    doc = {"what": "L0.14 part 2, INFO (no gate): the Crazyflie repository's offline planner (plan_guard, from a copy) at the "
                   "Starling's 1.10 m filter distance. Simulated matches on the planner's stand-in aircraft; not a flight result.",
           "smoke_not_of_record": a.matches is not None or bool(a.cases), "kind_filter": a.kind, "config": str(a.config),
           "config_sha256": hashlib.sha256(Path(a.config).read_bytes()).hexdigest(), "settings": cfg, "provenance": prov,
           "repo_untouched": untouched, "repo_status_after": after, "machine": platform.node(),
           "seconds": time.time() - t0, "cases": results}
    (run / "arena.json").write_text(json.dumps(doc, indent=1))
    print(f"wrote {run / 'arena.json'}; Crazyflie repository untouched: {untouched} ({doc['seconds']:.0f} s)")
    return EXIT_OK if untouched else EXIT_CONTROL_FAILED


if __name__ == "__main__":
    sys.exit(main())
