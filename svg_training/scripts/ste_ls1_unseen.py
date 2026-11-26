#!/usr/bin/env python
"""STE route 3, stage LS1, job LS1.4-H: the scores of the LS1.4 teams against players of no pool (INFO; task LS1-M4-T6
of ste_learning/drafts/LS1_TASK_PLAN.md, OP-31: its own script, so the read ``ste_ls1_read.py`` stays play-free;
design ste_learning/drafts/LS_EXECUTION_WORKFLOW.md section 6). Scoring only, no training; CPU, the device of record.

    ste_ls1_unseen.py --manifest <unseen.toml> --out <folder>

The manifest names finished run folders of ``scripts/ste_exploit_l012.py`` (absolute, or relative to svg_training/),
each launched through ``scripts/ste_job.py`` (its ``exit_code`` file)::

    [route1]                     # configs/ste_l3/velocity_gates.toml, variant base: the L5.1 runs (both required)
    guard = "..."; strike = "..."
    [route2.s1]                  # the scripts fly the chosen skill (configs/ste_l3/skills_gates.toml, variant base)
    guard = "..."; strike = "..."
    [route2.s2]                  # configs/ste_ls1/skills_seed2_gates.toml, variant base
    [route3.s1]                  # the skill network flies it (configs/ste_ls1/heads_gates.toml, variant base)
    [route3.s2]                  # configs/ste_ls1/heads_gates.toml, variant base_s2

The gate files and variants of the arms are the read's (``ste_ls1_read.GATE_FILES``, ``VARIANTS``); route 1's is fixed
here (``ROUTE1_GATES``). Each route team named (2 arms x 2 training pairs x 2 sides at most; a table or side not given
is listed as not given) plays ONE cell against the other side's route 1 team (the velocity route's trained team: a
player that was in no training pool of route 2 or route 3) on the reference's first ``[run] eval_games`` starts:
``exploit.play_cells`` with the route team as the learner (``exploit_train.skill_team_from_modules``, the gate file's
dispatch: the scripts' or the skill network's) and route 1's team as a named player (``exploit_train.team_from_modules``,
``hidden`` from route 1's gate file), both held ``[trainer] decision_ticks`` ticks in that one call (one hold per call;
the route team holds its choice and flies the chosen skill closed loop). One call per route team, so every team plays
at the same batch shape.

Refused (exit 2, nothing played or written): a manifest key that is not a route, pair or side, or no route team; a gate
file that does not load, still holds a ``FILL_`` mark, is not its arm's route (route 1: the velocity route), or whose
game file is off its pin; route 3's skill networks off their pins (C5, the driver's ``net_file_problems``); gate files
that do not share the game file, the scoring starts, the team size, ``eval_games``, ``ticks_cap`` or ``decision_ticks``
(the cell would not be one game); a run that did not work (no ``exit_code`` 0, a failed control), whose results.json is
not complete, ran under another gate file, side, variant, training seed or scoring starts, or trained short of its
game-step budget; a route 1 results.json with a skills ``[learner]`` table, a route 2 or 3 one whose table is not its
gate file's (``ste_ls1_read.check_learner``: route 3 carries the network and its sha256); a checkpoint the route's
loader refuses (a skills checkpoint as route 1, a velocity checkpoint as a route team, one arm's checkpoint under the
other arm's skill lists); an ``--out`` that already holds results.json or controls.json.

Controls (``scoring.plumbing_controls``, every cell: paired starts, one for one, no non-finite action): a failure exits
6, a non-finite action 5; controls.json and the per-game files are written, no score. Writes <out>/games/<arm>_<pair>_
<side>.npz as each cell is played, controls.json, results.json (per team: wins k of n with the Wilson 95 % interval, an
unfinished game counting as no win; how the games ended; the one-opponent pooled row of ``scoring.pooled_row``, the
shape of a run's pooled row; per training pair and side, route 3 minus route 2 start by start, ``compare.
paired_difference``; ``complete`` last) and results.md. INFO: no verdict and no margin. Results are "observed in the
training simulator"; not for flight."""
from __future__ import annotations

import argparse
import pickle
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import torch  # noqa: E402

import ste_exploit_l012 as driver  # noqa: E402  (the networks' preflight, the simulator words, JSON writing)
import ste_l6_read as l6  # noqa: E402  (the stage checks: exit codes, gate sha256, JSON reading)
import ste_ls1_read as rd  # noqa: E402  (the arms' gate files and variants, the learner check)
from svg_training.core.rewards import GUARD_WIN, RUNNING, STRIKE_WIN  # noqa: E402
from svg_training.ste import compare, exploit, exploit_train, scoring, skills  # noqa: E402

EXIT_DONE, EXIT_REFUSED = rd.EXIT_DONE, rd.EXIT_REFUSED
Refused = rd.Refused
DEVICE = "cpu"                                   # the device of record (plan LS1-M4-T6)
ROUTE1 = "route1"
ROUTE1_GATES = ROOT / "configs" / "ste_l3" / "velocity_gates.toml"     # L5.1, the velocity route
ROUTE1_VARIANT = "base"
ROUTE1_PREFIX = "route1:"                        # route 1's cell names: never a script's name or the exploiter's
ARMS, PAIRS, SIDES = rd.ARMS, rd.PAIRS, ("guard", "strike")
SIDE_NAME = rd.SIDE_NAME
RESULTS, CONTROLS, MD, GAMES = "results.json", "controls.json", "results.md", "games"
AGENT = "agent_final.pt"
PHASE = "unseen"
LABEL = "INFO"
STATUS = "observed in the training simulator; not for flight"
ARM_NAME = rd.ARM_NAME
CANNOT_SHOW = [
    "one opponent per side: route 1's trained team of that side (one seed), not a population of unseen players",
    "route 1 trained in the same game and against the same scripts: an unseen player, not an unseen game condition",
    "two training pairs per arm: a spread over two seeds, not a population",
    "tier 1 only; no flight"]


def other(side: str) -> str:
    return "strike" if side == "guard" else "guard"


def route1_name(side: str) -> str:
    return ROUTE1_PREFIX + side


def stem(arm: str, pair: str, side: str) -> str:
    return f"{arm}_{pair}_{side}"


# ------------------------------------------------------------------------------------------------ the manifest
def teams_of(m: dict) -> list[tuple[str, str, str]]:
    """The route teams the manifest names, in (arm, pair, side) order; Refused for any other key."""
    unknown = sorted(set(m) - {ROUTE1, *ARMS})
    if unknown:
        raise Refused(f"the manifest's tables {unknown} are not {ROUTE1} or an arm {list(ARMS)}")
    r1 = m.get(ROUTE1)
    if not isinstance(r1, dict) or sorted(r1) != sorted(SIDES) or not all(isinstance(v, str) for v in r1.values()):
        raise Refused(f"the manifest's [{ROUTE1}] names exactly one folder per side {list(SIDES)}")
    teams = []
    for arm in ARMS:
        tab = m.get(arm, {})
        bad = sorted(set(tab) - set(PAIRS)) if isinstance(tab, dict) else [arm]
        if bad:
            raise Refused(f"the manifest's [{arm}] holds {bad}, not training pairs {list(PAIRS)}")
        for pair in PAIRS:
            sub = tab.get(pair, {})
            bad = sorted(set(sub) - set(SIDES)) if isinstance(sub, dict) else [pair]
            if bad or not all(isinstance(v, str) for v in sub.values()):
                raise Refused(f"the manifest's [{arm}.{pair}] holds {bad or sub}, not folders by side {list(SIDES)}")
            teams += [(arm, pair, side) for side in SIDES if side in sub]
    if not teams:
        raise Refused("the manifest names no route team")
    return teams


# ------------------------------------------------------------------------------------------------ the gate files
def load_route1():
    path = Path(ROUTE1_GATES)
    try:
        gates = exploit.load_gates(path)
    except (ValueError, OSError) as err:
        raise Refused(f"{ROUTE1}: the gate file {rd.rel(path)} does not load: {err}") from err
    if gates.learner.skills:
        raise Refused(f"{ROUTE1}: the gate file {rd.rel(path)} is not the velocity route ([learner] action "
                      f"{gates.learner.action!r})")
    left = exploit.unfilled(gates)
    if left:
        raise Refused(f"{ROUTE1}: the gate file {rd.rel(path)} still holds FILL_ marks: {left}")
    if ROUTE1_VARIANT not in gates.variants:
        raise Refused(f"{ROUTE1}: the gate file {rd.rel(path)} has no variant {ROUTE1_VARIANT!r}")
    return gates


def one_game(gates, variant: str) -> dict:
    """What every cell of the job must share, from one gate file and variant."""
    game = gates.games[gates.variants[variant]["game"]]
    return {"game file sha256": game.sha256, "reference sha256": gates.reference["sha256"],
            "scoring starts (start_sha256)": gates.reference["start_sha256"], "size": gates.run["size"],
            "eval_games": int(gates.run["eval_games"]), "ticks_cap": int(gates.run["ticks_cap"]),
            "decision_ticks": int(gates.trainer["decision_ticks"])}


def check_gates(name: str, gates, variant: str, want: dict) -> None:
    problems = exploit.game_file_problems(gates)
    if problems:
        raise Refused(f"{name}: the game file(s) differ from the gate file: " + "; ".join(problems))
    problems = driver.net_file_problems(gates)
    if problems:
        raise Refused(f"{name}: the skill network(s) of [learner.skill_net] (C5): " + "; ".join(problems))
    got = one_game(gates, variant)
    off = [k for k in want if got[k] != want[k]]
    if off:
        raise Refused(f"{name}: {off} differ from route 1's gate file ({[got[k] for k in off]} against "
                      f"{[want[k] for k in off]}): not one game")


# ------------------------------------------------------------------------------------------------ the run folders
def check_folder(value: str, gates, variant: str, side: str, arm: str, stage: str) -> dict:
    """A finished run of record of ``side`` under ``gates`` and ``variant``: its folder, checkpoint and training seed."""
    folder = l6.path_of(value)
    if not folder.is_dir():
        raise Refused(f"{stage}: {rd.rel(folder)} does not exist")
    why = l6.stopped(folder, stage)
    if why:
        raise Refused(f"{stage}: {why}: a run that did not work is not scored")
    res = l6.load_json(folder / RESULTS, stage)
    if res.get("complete") is not True:
        raise Refused(f"{stage}: results.json is not complete")
    l6.check_sha(res.get("gates_sha256"), gates, stage)
    seed = int(gates.variants[variant]["train_seed"][side])
    for key, want in (("side", side), ("variant", variant), ("train_seed", seed)):
        if res.get(key) != want:
            raise Refused(f"{stage}: results.json {key} {res.get(key)!r}, expected {want!r}")
    if res.get("reference", {}).get("start_sha256") != gates.reference["start_sha256"]:
        raise Refused(f"{stage}: scored on other starts than the gate file's reference")
    if res.get("budget_reached") is not True:
        raise Refused(f"{stage}: trained short of its game-step budget ({res.get('train_stop')})")
    if arm == ROUTE1:
        if "learner" in res:
            raise Refused(f"{stage}: results.json carries a skills [learner] table; route 1 is the velocity route")
        learner = "velocity"
    else:
        learner = rd.check_learner(res.get("learner"), gates, arm, stage)
    agent = folder / AGENT
    if not agent.is_file():
        raise Refused(f"{stage}: {AGENT} is missing")
    return {"folder": rd.rel(folder), "path": agent, "agent_sha256": exploit.sha256_file(agent), "train_seed": seed,
            "learner": learner}


def build_team(entry: dict, gates, variant: str, side: str, arm: str, n: int, name: str, stage: str):
    """The run's trained team on the CPU through its route's loader (route 1: ``team_from_modules``; route 2 and 3:
    ``skill_team_from_modules`` on the gate file's dispatch, built for ``n`` games)."""
    try:
        saved = torch.load(entry["path"], map_location=DEVICE, weights_only=False)
    except (OSError, RuntimeError, EOFError, pickle.UnpicklingError) as err:
        raise Refused(f"{stage}: {AGENT} does not load: {err}") from err
    hidden = list(gates.trainer["hidden"])
    try:
        if arm == ROUTE1:
            team = exploit_train.team_from_modules(side, saved, hidden, DEVICE)
        else:
            dispatch = skills.two_level_dispatch(gates.learner, gates.players, side, exploit.variant_cfg(gates, variant),
                                                 n, DEVICE, entry["train_seed"])
            team = exploit_train.skill_team_from_modules(side, saved, hidden, dispatch, DEVICE)
    except (ValueError, RuntimeError, KeyError, TypeError, AttributeError) as err:
        raise Refused(f"{stage}: {AGENT}: the route's loader refuses it: {err}") from err
    team.name = name
    return team


# ------------------------------------------------------------------------------------------------ the job
def prepare(m: dict) -> dict:
    """Every check and every team, before any game is played."""
    teams = teams_of(m)
    g1 = load_route1()
    want = one_game(g1, ROUTE1_VARIANT)
    check_gates(ROUTE1, g1, ROUTE1_VARIANT, want)
    gates = {}
    for arm, pair, _ in teams:
        if (arm, pair) not in gates:
            gates[(arm, pair)] = rd.load(arm, pair)
            check_gates(f"{arm} {pair}", gates[(arm, pair)], rd.VARIANTS[arm][pair], want)
    n = want["eval_games"]
    route1 = {}
    for side in SIDES:
        stage = f"LS1.4-H route 1 {SIDE_NAME[side]} run"
        entry = check_folder(m[ROUTE1][side], g1, ROUTE1_VARIANT, side, ROUTE1, stage)
        route1[side] = {**entry, "team": build_team(entry, g1, ROUTE1_VARIANT, side, ROUTE1, n, route1_name(side),
                                                     stage)}
    rows = []
    for arm, pair, side in teams:
        g, variant = gates[(arm, pair)], rd.VARIANTS[arm][pair]
        stage = f"LS1.4-H {arm} {pair} {SIDE_NAME[side]} run"
        entry = check_folder(m[arm][pair][side], g, variant, side, arm, stage)
        rows.append({"arm": arm, "pair": pair, "side": side, "variant": variant, "gates": g, **entry,
                     "team": build_team(entry, g, variant, side, arm, n, f"{arm}:{pair}:{side}", stage)})
    ref_path = ROOT / g1.reference["file"]
    why = scoring.sha_problem(ref_path, g1.reference["sha256"], "the reference")
    if why:
        raise Refused(why)
    ref = exploit.load_reference(ref_path)
    if ref.start_sha256 != g1.reference["start_sha256"]:
        raise Refused(f"the reference's starts sha256 {ref.start_sha256} is not the gate files' "
                      f"{g1.reference['start_sha256']}")
    given = {(r["arm"], r["pair"], r["side"]) for r in rows}
    return {"g1": g1, "gates": gates, "route1": route1, "rows": rows, "ref": ref, "n": n, "game": want,
            "not_given": [f"{a} {p} {s}" for a in ARMS for p in PAIRS for s in SIDES if (a, p, s) not in given]}


def play(job: dict, out: Path) -> tuple[dict, dict]:
    """One cell per route team (one ``play_cells`` call each, both teams held ``decision_ticks``); each batch's
    per-game file is written as it is played. Returns ({team key: the cell's per-game arrays}, the controls)."""
    ref, n = job["ref"], job["n"]
    hold, ticks, size = job["game"]["decision_ticks"], job["game"]["ticks_cap"], job["game"]["size"]
    (out / GAMES).mkdir(parents=True, exist_ok=True)
    played, controls = {}, {}
    for r in job["rows"]:
        side = r["side"]
        opp = route1_name(other(side))
        cell = (exploit.EXPLOITER, opp) if side == "guard" else (opp, exploit.EXPLOITER)
        cfg = exploit.variant_cfg(r["gates"], r["variant"])
        pg = exploit.play_cells(cfg, size, ref, [cell], n, DEVICE, int(ref.meta["seed"]), ticks, learner=r["team"],
                                hold_ticks=hold, players={opp: job["route1"][other(side)]["team"]})
        key = stem(r["arm"], r["pair"], side)
        scoring.save_batch(out / GAMES / f"{key}.npz", pg)
        controls.update(scoring.plumbing_controls(pg, ref, n, PHASE, suffix=f"_{key}"))
        played[key] = {**exploit.slice_cell(pg, 0, n), "game_ticks": int(pg["game_ticks"]), "cell": cell}
    return played, controls


def wins_of(pg: dict, side: str) -> np.ndarray:
    return np.asarray(pg["outcome"]) == (GUARD_WIN if side == "guard" else STRIKE_WIN)


def row_of(r: dict, pg: dict, job: dict) -> dict:
    side, n = r["side"], job["n"]
    opp = route1_name(other(side))
    won = wins_of(pg, side)
    r1 = job["route1"][other(side)]
    return {"arm": r["arm"], "pair": r["pair"], "side": side, "team": SIDE_NAME[side], "folder": r["folder"],
            "agent_sha256": r["agent_sha256"], "gates": rd.rel(r["gates"].path), "gates_sha256": r["gates"].sha256,
            "variant": r["variant"], "train_seed": r["train_seed"], "learner": r["learner"],
            "opponent": {"name": opp, "team": f"route 1's trained {SIDE_NAME[other(side)]} team (velocity route)",
                         "folder": r1["folder"], "agent_sha256": r1["agent_sha256"], "train_seed": r1["train_seed"]},
            "cell": list(pg["cell"]), **scoring.rate(int(won.sum()), n), "rate": float(won.mean()),
            "unfinished": int(np.sum(np.asarray(pg["outcome"]) == RUNNING)),
            "end_reasons": scoring.end_reasons(pg, pg["game_ticks"]), "length_median_s": scoring.length_median_s(pg),
            "pooled": scoring.pooled_row({opp: won}),
            "games_file": f"{GAMES}/{stem(r['arm'], r['pair'], side)}.npz", "label": LABEL}


def paired(played: dict, job: dict) -> dict:
    """Per training pair and side with both arms given: route 3 minus route 2, start by start (the same starts and the
    same route 1 opponent)."""
    out = {}
    for pair in PAIRS:
        for side in SIDES:
            keys = [stem(arm, pair, side) for arm in ("route3", "route2")]
            if all(k in played for k in keys):
                d = compare.paired_difference(wins_of(played[keys[0]], side), wins_of(played[keys[1]], side))
                out.setdefault(pair, {})[side] = {
                    **d, "what": f"route 3 minus route 2, {SIDE_NAME[side]} team, start by start, against route 1's "
                                 f"{SIDE_NAME[other(side)]} team", "label": LABEL}
    return out


def render(res: dict) -> str:
    lines = [f"Simulator: tier 1 training simulator; {STATUS}. Label: {res['label']} (no verdict, no margin). "
             f"{res['review']}", "",
             f"Each route team against the other side's trained team of route 1 (the velocity route, a player of no "
             f"training pool), {res['games_per_cell']:,} games on the reference's first starts, both held "
             f"{res['hold_ticks']} ticks, on the CPU. Route 2: {ARM_NAME['route2']}; route 3: {ARM_NAME['route3']}.",
             "", "| Arm | Pair | Team | Against | Wins | Wilson 95 % | Unfinished |", "|---|---|---|---|---|---|---|"]
    for r in res["teams"]:
        lines.append(f"| {r['arm']} | {r['pair']} | {r['team']} | {r['opponent']['name']} | {r['k']:,} of {r['n']:,} "
                     f"| {r['ci'][0]:.3f}-{r['ci'][1]:.3f} | {r['unfinished']} |")
    lines.append("")
    for pair, by_side in res["paired"].items():
        for side, d in by_side.items():
            lines.append(f"- Pair {pair}, {SIDE_NAME[side]} team, route 3 minus route 2 start by start (INFO): "
                         f"{d['diff']:+.4f} [{d['ci'][0]:+.4f}, {d['ci'][1]:+.4f}], {d['word']}.")
    if res["not_given"]:
        lines.append(f"- Not given in the manifest: {', '.join(res['not_given'])}.")
    lines += ["", "## What it cannot show", ""] + [f"- {x}" for x in res["cannot_show"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ste_ls1_unseen.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        for name in (RESULTS, CONTROLS):
            if (a.out / name).exists():
                raise Refused(f"{rd.rel(a.out)} already holds {name}: a new score needs a new folder")
        try:
            m = tomllib.loads(a.manifest.read_text())
        except (OSError, tomllib.TOMLDecodeError) as err:
            raise Refused(f"the manifest {rd.rel(a.manifest)} does not load: {err}") from err
        job = prepare(m)
    except Refused as err:
        print(f"refused: {err}", file=sys.stderr, flush=True)
        return EXIT_REFUSED
    a.out.mkdir(parents=True, exist_ok=True)
    played, controls = play(job, a.out)
    driver.write_json(a.out / CONTROLS, controls)
    code = scoring.ending(controls)
    if code is not None:
        bad = [k for k, v in controls.items() if v["status"] != scoring.PASS]
        print(f"control not PASS: {bad}; no score is published (exit {code})", file=sys.stderr, flush=True)
        return code
    rows = [row_of(r, played[stem(r["arm"], r["pair"], r["side"])], job) for r in job["rows"]]
    g1, ref = job["g1"], job["ref"]
    res = {"what": "STE LS1.4-H: the LS1.4 route teams against route 1's trained teams, players of no training pool "
                   "(scripts/ste_ls1_unseen.py); observed in the training simulator",
           "status": STATUS, "label": LABEL, "review": "Draft until reviewed (R22).", "simulator": driver.SIMULATOR,
           "device": DEVICE, "games_per_cell": job["n"], "hold_ticks": job["game"]["decision_ticks"],
           "ticks_cap": job["game"]["ticks_cap"], "seed": int(ref.meta["seed"]),
           "reference": {"file": g1.reference["file"], "sha256": g1.reference["sha256"],
                         "start_sha256": g1.reference["start_sha256"]},
           "game_sha256": job["game"]["game file sha256"],
           "manifest": rd.rel(a.manifest), "manifest_sha256": exploit.sha256_file(a.manifest),
           "route1": {side: {"folder": e["folder"], "agent_sha256": e["agent_sha256"], "train_seed": e["train_seed"],
                             "gates": rd.rel(g1.path), "gates_sha256": g1.sha256, "variant": ROUTE1_VARIANT}
                      for side, e in job["route1"].items()},
           "teams": rows, "not_given": job["not_given"], "paired": paired(played, job), "controls": controls,
           "cannot_show": CANNOT_SHOW}
    res["complete"] = True                       # written last: a crash before here leaves no results.json
    driver.write_json(a.out / RESULTS, res)
    (a.out / MD).write_text(render(res))
    for r in rows:
        print(f"{r['arm']} {r['pair']} {r['team']} team v {r['opponent']['name']}: {r['k']} of {r['n']}")
    return EXIT_DONE


if __name__ == "__main__":
    sys.exit(main())
