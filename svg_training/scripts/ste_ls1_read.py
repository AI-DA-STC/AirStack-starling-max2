#!/usr/bin/env python
"""STE route 3, stage LS1, job group LS1.4: the read of LS1.4 (task LS1-M4-T5 of
ste_learning/drafts/LS1_TASK_PLAN.md; design ste_learning/drafts/LS_EXECUTION_WORKFLOW.md section 6). Route 3 (the
distilled skill network flies the chosen skill) against route 2 (the scripts fly it), training pair by training pair.
CPU, saved files only: no training, no game is played.

    ste_ls1_read.py --manifest <read.toml> --out <folder>

The manifest names the folders (absolute, or relative to svg_training/), each launched through
``scripts/ste_job.py`` (its ``exit_code`` file), per arm and training pair::

    [route2.s1]                  # configs/ste_l3/skills_gates.toml, variant base (L3.3 pilot, L3.5 run 0, L5.2)
    pilot = "..."; run0 = "..."; guard = "..."
    strike = "..."               # optional: a Strike run of record (INFO)
    [route2.s2]                  # configs/ste_ls1/skills_seed2_gates.toml, variant base; pilot: route 2's L3.3 pilot
    [route3.s1]                  # configs/ste_ls1/heads_gates.toml, variant base
    [route3.s2]                  # configs/ste_ls1/heads_gates.toml, variant base_s2 (its own run 0, owner R46)

The gate files are fixed here (``GATE_FILES``), not chosen by the manifest. The rule is the route 3 gate file's
``[reading]`` (hashed with it before the pilot; no margin is typed here, R38). Per side and pair a score:

* Strike: the run 0 cell. A pair's score is the mean of its run 0's last ``last_reads`` reads (reaches against the
  parked Guard over the reference's first starts); the margin is ``margin_cell`` (OP-34). Under option B (owner R46)
  each pair has its own run 0 on both arms, so the read is two pairs against two.
* Guard: the pooled row of the final INFO batch (the trained Guard team against every script of the pool, on the
  reference starts), paired start by start (OP-30 (a)); the margin is ``margin_pooled``. The per-cell gaps against
  ``margin_cell`` are INFO, never gated.

The rule, on exact fractions of the counts (``rule``): NO DROP BEYOND THE MARGIN when route 3's mean over the pairs is
at least route 2's mean less the margin and each route 3 pair is at least route 2's lowest pair less the margin;
BELOW when route 3's mean is under route 2's mean less twice the margin; otherwise INCONCLUSIVE, and a third training
pair per arm is needed. Beside each score ``min_last_reads``: the lowest of the last ``last_reads`` reads (run 0 reads
for Strike; ``curve.json`` reads for Guard, INFO).

Refused (exit 2, nothing written): a gate file that does not load or still holds a ``FILL_`` mark; a stage that did not
work (a failed control, a crash, a stop: this read words none of them); a run 0 or run short of its game-step budget;
a pairing that does not hold between the arms of a pair (training seed, run 0 seed and variant, pool seed, recipe,
game-step budget, game file, scoring starts, run 0 checkpoints and read sizes); a route 3 file flown without the skill
network or with another network sha256; a learner table that is not its gate file's; route 2 seed 2's pilot unless it
ran under the file it names (route 2's L3.3 pilot, under configs/ste_l3/skills_gates.toml) and its learner table is
seed 2's. The learner table itself is never copied into the read: it writes the check result only.

Writes <out>/read.json and read.md; exit 0 done, 2 refused. Results are "observed in the training simulator"; not for
flight."""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402

import ste_l6_read as l6  # noqa: E402  (the L6.1 reader's stage checks: exit codes, pilots, runs, same starts)
from svg_training.ste import compare, exploit, skills  # noqa: E402

EXIT_DONE, EXIT_REFUSED = l6.EXIT_DONE, l6.EXIT_REFUSED
Refused = l6.Refused
ARMS = ("route2", "route3")
PAIRS = ("s1", "s2")
SIDES = ("strike", "guard")
SIDE_NAME = {"guard": "Guard", "strike": "Strike"}
ARM_NAME = {"route2": "route 2 (the scripts fly the chosen skill)",
            "route3": "route 3 (the distilled skill network flies the chosen skill)"}
CONFIGS = ROOT / "configs"
GATE_FILES = {"route2": {"s1": CONFIGS / "ste_l3" / "skills_gates.toml",
                         "s2": CONFIGS / "ste_ls1" / "skills_seed2_gates.toml"},
              "route3": {"s1": CONFIGS / "ste_ls1" / "heads_gates.toml",
                         "s2": CONFIGS / "ste_ls1" / "heads_gates.toml"}}
VARIANTS = {"route2": {"s1": "base", "s2": "base"}, "route3": {"s1": "base", "s2": "base_s2"}}
PILOT_RAN_UNDER = {("route2", "s2"): ("route2", "s1")}     # route 2 seed 2 runs on route 2's L3.3 pilot
READING_ARM = "route3"
RUN0_FILE, CURVE_FILE = "learner_control.json", "curve.json"
MARGIN_OF = {"strike": "margin_cell", "guard": "margin_pooled"}
NO_DROP, BELOW, INCONCLUSIVE = "NO DROP BEYOND THE MARGIN", "BELOW", "INCONCLUSIVE"
BELOW_FACTOR = 2                   # "below": route 3's mean under route 2's by more than twice the margin
STATUS = "observed in the training simulator; not for flight"
THIRD_PAIR = ("a third training pair per arm (route 2 and route 3, the same seeds on both arms) is needed; its seeds "
              "are set in a gate file before it runs, and it is labelled an added read")
SCRIPTS_BEST = ("the scripts' best single fixed choice on the reference cells (a route 3 run's results.json computes "
                "it from the scripts' reference cells, not from the network): INFO")
DEPARTURE = ("Departure from workflow section 6 (W3): a run of record saves only curve.json reads (256 games on the "
             "curve starts against one opponent) and one final batch, so its last reads are not paired start by "
             "start. The Guard score is the final batch's pooled row, paired start by start (OP-30 (a)); the lowest "
             "and the mean of the last curve.json reads are written beside it as INFO. The Strike score is the run 0 "
             "cell (its reads are on the reference starts).")
CANNOT_SHOW = [
    "two training pairs per arm: a spread over two seeds, not a population",
    "the run 0 cell is one opponent (the parked Guard); the Strike runs of record are INFO",
    "tier 1 training only; no flight",
    "the network's own errors beyond what LS1.2's equivalence read bounds",
    "the scripted opponents of the pool only (no unseen opponent in this read)"]


# ------------------------------------------------------------------------------------------------ helpers
def rel(path) -> str:
    """``path`` repository-relative; outside the repository its name only (no machine or user name in a file)."""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return f"(outside svg_training)/{p.name}"


def mean(values) -> Fraction:
    values = list(values)
    return sum(values, Fraction(0)) / len(values)


def exact(x: Fraction) -> str:
    return f"{x.numerator}/{x.denominator}"


def rule(route3: list, route2: list, margin: Fraction) -> str:
    """The LS1.4 rule on exact fractions: ``route3`` and ``route2`` the pairs' scores, ``margin`` the gate file's."""
    m3, m2 = mean(route3), mean(route2)
    if m3 >= m2 - margin and min(route3) >= min(route2) - margin:
        return NO_DROP
    if m3 < m2 - BELOW_FACTOR * margin:
        return BELOW
    return INCONCLUSIVE


def load(arm: str, pair: str):
    path = Path(GATE_FILES[arm][pair])
    try:
        gates = exploit.load_gates(path)
    except (ValueError, OSError) as err:
        raise Refused(f"{arm} {pair}: the gate file {rel(path)} does not load: {err}") from err
    left = exploit.unfilled(gates)
    if left:
        raise Refused(f"{arm} {pair}: the gate file {rel(path)} still holds FILL_ marks: {left} (R38: the read waits "
                      f"for the fills)")
    net = gates.learner.skill_source == skills.NET_SOURCE
    if net != (arm == "route3"):
        raise Refused(f"{arm} {pair}: the gate file {rel(path)} is " + ("" if net else "not ") + "a skill network file")
    return gates


def check_learner(got, gates, arm: str, stage: str) -> str:
    """The file's learner table against its gate file's; route 3 must carry the network and its sha256. Returns the
    check result written into the read (never the table)."""
    want = skills.learner_table(gates.learner)
    if arm == "route3":
        if not isinstance(got, dict) or got.get("skill_source") != skills.NET_SOURCE:
            raise Refused(f"{stage}: a route 3 file flown without the skill network")
        if got.get("skill_net_sha256") != want["skill_net_sha256"]:
            raise Refused(f"{stage}: flown with another skill network sha256 {got.get('skill_net_sha256')}, the gate "
                          f"file's is {want['skill_net_sha256']}")
    if got != want:
        raise Refused(f"{stage}: its [learner] table is not its gate file's")
    return "net, sha256 as the gate file" if arm == "route3" else "scripts, as the gate file"


def did_not_work(stage: str, why: str):
    raise Refused(f"{stage}: {why}: a stage that did not work is not read here")


# ------------------------------------------------------------------------------------------------ the stages
def read_pilot(m: dict, arm: str, pair: str, gates, under, stage: str) -> dict:
    folder = l6.need(m, "pilot", stage)
    why = l6.read_pilot(folder, under, stage)
    if why:
        did_not_work(stage, why)
    data = l6.load_json(folder / "pilot.json", stage)
    learner = check_learner(data.get("learner"), gates, arm, stage)
    problem = exploit.recipe_problem(gates, data)
    if problem:
        raise Refused(f"{stage}: {problem}")
    return {"folder": rel(folder), "ran_under": rel(under.path), "learner": learner}


def read_run0(m: dict, arm: str, pair: str, gates, variant: str, last: int, stage: str) -> dict:
    folder = l6.need(m, "run0", stage)
    why, status = l6.read_run0(folder, gates, stage)
    if why:
        did_not_work(stage, why)
    data = l6.load_json(folder / RUN0_FILE, stage)
    if data.get("variant") != variant:
        raise Refused(f"{stage}: run 0 trained variant {data.get('variant')!r}, this pair's is {variant!r}")
    seed = exploit.run0_seed(gates, variant)
    if data.get("train_seed") != seed:
        raise Refused(f"{stage}: run 0 train_seed {data.get('train_seed')}, the gate file's for variant {variant} is "
                      f"{seed}")
    if data.get("recipe") != exploit.recipe_label(gates, "strike", variant):
        raise Refused(f"{stage}: run 0 recipe {data.get('recipe')!r} is not the gate file's")
    learner = check_learner(data.get("learner"), gates, arm, stage)
    if data.get("budget_reached") is not True:
        raise Refused(f"{stage}: run 0 trained short of its game-step budget ({data.get('train_stop')}): its last "
                      f"reads are not at the budget's checkpoints")
    reads, marks = list(data.get("reads") or []), list(data.get("checkpoints") or [])
    if len(reads) < last:
        raise Refused(f"{stage}: run 0 has {len(reads)} reads, the rule takes the last {last}")
    if not marks or reads[-1]["update"] != marks[-1]:
        raise Refused(f"{stage}: run 0 has no read at its final checkpoint (checkpoints {marks})")
    used = reads[-last:]
    rates = [Fraction(int(r["trained"]["k"]), int(r["trained"]["n"])) for r in used]
    return {"folder": rel(folder), "status": status, "variant": variant, "train_seed": int(seed),
            "recipe": data.get("recipe"), "opponent": data.get("opponent"), "checkpoints": marks, "learner": learner,
            "reads_used": [{"update": int(r["update"]), "game_steps": int(r["game_steps"]),
                            "k": int(r["trained"]["k"]), "n": int(r["trained"]["n"])} for r in used],
            "score": mean(rates), "min_last_reads": min(rates)}


def read_run(m: dict, key: str, arm: str, pair: str, gates, variant: str, side: str, last: int, stage: str) -> dict:
    """A run of record: ``ste_l6_read.read_main`` (exit, results complete, gate sha, side, starts, budget, INFO cells,
    pooled rate recomputed) and this pair's variant, training seed, recipe and learner; its score is the pooled row of
    the final INFO batch, exact from the per-game file; ``curve.json``'s last reads beside it."""
    folder = l6.need(m, key, stage)
    why, run = l6.read_main(folder, gates, side, stage)
    if why:
        did_not_work(stage, why)
    res = run["results"]
    if res.get("variant") != variant:
        raise Refused(f"{stage}: a run of variant {res.get('variant')!r}, this pair's is {variant!r}")
    seed = int(gates.variants[variant]["train_seed"][side])
    if res.get("train_seed") != seed:
        raise Refused(f"{stage}: train_seed {res.get('train_seed')}, the gate file's is {seed}")
    if res.get("recipe") != exploit.recipe_label(gates, side, variant):
        raise Refused(f"{stage}: recipe {res.get('recipe')!r} is not the gate file's")
    learner = check_learner(res.get("learner"), gates, arm, stage)
    curve = l6.load_json(folder / CURVE_FILE, stage)
    if not isinstance(curve, list) or len(curve) < last:
        raise Refused(f"{stage}: {CURVE_FILE} holds fewer than {last} reads")
    curve_rates = [Fraction(int(p["k"]), int(p["n"])) for p in curve[-last:]]
    won = sum(int(np.count_nonzero(run["wins"][o])) for o in run["members"])
    best = res.get("best_single_choice", {})
    return {"folder": rel(folder), "variant": variant, "train_seed": seed, "recipe": res.get("recipe"),
            "learner": learner, "score": Fraction(won, len(run["members"]) * run["n"]),
            "min_last_reads": min(curve_rates), "curve_mean_last_reads": mean(curve_rates),
            "curve_updates": [int(p["update"]) for p in curve[-last:]],
            "best_single_choice": {"best": best.get("best"), "label": SCRIPTS_BEST},
            "choice_share": {o: compare.overall_share(e) for o, e in res.get("choice_by_decision", {}).items()},
            "run": run}


# ------------------------------------------------------------------------------------------------ the pairing
def same(what: str, a, b, pair: str) -> None:
    if a != b:
        raise Refused(f"pair {pair}: {what} not paired between the arms (route 3 {a!r}, route 2 {b!r})")


def pair_gates(g3, v3: str, g2, v2: str, pair: str) -> None:
    """What the two arms of a pair must share by their gate files."""
    same("the pool ([pool] enabled, seed)", (g3.pool.get("enabled"), g3.pool.get("seed")),
         (g2.pool.get("enabled"), g2.pool.get("seed")), pair)
    same("[trainer] game_steps_per_run", g3.trainer["game_steps_per_run"], g2.trainer["game_steps_per_run"], pair)
    for side in SIDES:
        same(f"the {SIDE_NAME[side]} recipe", exploit.recipe_label(g3, side, v3), exploit.recipe_label(g2, side, v2),
             pair)
        same(f"the {SIDE_NAME[side]} train_seed", g3.variants[v3]["train_seed"][side],
             g2.variants[v2]["train_seed"][side], pair)
    same("the run 0 seed", exploit.run0_seed(g3, v3), exploit.run0_seed(g2, v2), pair)
    g3game, g2game = g3.games[g3.variants[v3]["game"]], g2.games[g2.variants[v2]["game"]]
    same("the game file sha256", g3game.sha256, g2game.sha256, pair)
    same("the scoring starts ([reference] start_sha256)", g3.reference["start_sha256"], g2.reference["start_sha256"],
         pair)
    same("eval_games", g3.run["eval_games"], g2.run["eval_games"], pair)
    same("[players]", g3.players, g2.players, pair)
    same("[run0] opponent", g3.run0["opponent"], g2.run0["opponent"], pair)


def pair_run0(r3: dict, r2: dict, pair: str) -> None:
    same("the run 0 train_seed", r3["train_seed"], r2["train_seed"], pair)
    same("the run 0 recipe", r3["recipe"], r2["recipe"], pair)
    same("the run 0 opponent", r3["opponent"], r2["opponent"], pair)
    same("the run 0 checkpoints", r3["checkpoints"], r2["checkpoints"], pair)
    same("the run 0 read updates", [x["update"] for x in r3["reads_used"]], [x["update"] for x in r2["reads_used"]],
         pair)
    same("the run 0 read games", [x["n"] for x in r3["reads_used"]], [x["n"] for x in r2["reads_used"]], pair)


def pair_runs(r3: dict, r2: dict, side: str, pair: str) -> dict:
    """Two runs of record of one side: the same starts and game (``ste_l6_read.same_starts``), seed and recipe; their
    per-start pooled difference and per-cell differences (INFO)."""
    a, b = r3["run"], r2["run"]
    l6.same_starts(a, b, f"pair {pair} {side} runs")
    same(f"the {SIDE_NAME[side]} train_seed", r3["train_seed"], r2["train_seed"], pair)
    same(f"the {SIDE_NAME[side]} recipe", r3["recipe"], r2["recipe"], pair)
    same(f"the {SIDE_NAME[side]} pool members", a["members"], b["members"], pair)
    d = compare.paired_difference(compare.per_start_mean(a["wins"], a["members"]),
                                  compare.per_start_mean(b["wins"], b["members"]))
    return {**d, "what": "route 3 minus route 2, the per-start mean over the pool's cells, start by start",
            "label": "INFO"}


def cell_gaps(r3: dict, r2: dict, margin_cell: Fraction) -> list:
    a, b = r3["run"], r2["run"]
    out = []
    for o in a["members"]:
        gap = Fraction(int(np.count_nonzero(a["wins"][o])) - int(np.count_nonzero(b["wins"][o])), a["n"])
        out.append({"opponent": o, **compare.paired_difference(a["wins"][o], b["wins"][o]),
                    "beyond_margin_cell": bool(gap < -margin_cell),
                    "label": "INFO, never gated (two pairs carry no per-cell verdict; OP-30)"})
    return out


# ------------------------------------------------------------------------------------------------ the read
def scored(entry: dict) -> dict:
    """An arm's entry as written: the exact score and the lowest read as floats beside their fractions."""
    out = {k: v for k, v in entry.items() if k not in ("run", "score", "min_last_reads", "curve_mean_last_reads",
                                                       "best_single_choice", "choice_share")}
    out.update(score=float(entry["score"]), score_exact=exact(entry["score"]),
               min_last_reads=float(entry["min_last_reads"]))
    if "curve_mean_last_reads" in entry:
        out["curve_mean_last_reads"] = float(entry["curve_mean_last_reads"])
        out["min_last_reads_note"] = "the lowest of the last curve.json reads (256 games, curve starts): INFO"
    return out


def verdict(side: str, entries: dict, margins: dict) -> dict:
    key = MARGIN_OF[side]
    margin = margins[key]
    r3 = [entries[p]["route3"]["score"] for p in PAIRS]
    r2 = [entries[p]["route2"]["score"] for p in PAIRS]
    word = rule(r3, r2, margin)
    m2 = mean(r2)
    out = {"word": word, "margin_key": key, "margin": float(margin),
           "mean": {"route2": float(m2), "route3": float(mean(r3))},
           "route2_lowest": float(min(r2)), "route3_lowest": float(min(r3)),
           "no_drop_needs": {"mean_at_least": float(m2 - margin), "each_pair_at_least": float(min(r2) - margin)},
           "below_when_mean_under": float(m2 - BELOW_FACTOR * margin)}
    if word == INCONCLUSIVE:
        out["next"] = THIRD_PAIR
    return out


def read(m: dict) -> dict:
    for arm in ARMS:
        for pair in PAIRS:
            if not isinstance(m.get(arm, {}).get(pair), dict):
                raise Refused(f"the manifest has no [{arm}.{pair}] table")
    gates = {(a, p): load(a, p) for a in ARMS for p in PAIRS}
    reading = gates[(READING_ARM, PAIRS[0])].reading
    if any(gates[(READING_ARM, p)].sha256 != gates[(READING_ARM, PAIRS[0])].sha256 for p in PAIRS):
        raise Refused("route 3's pairs name different gate files: one [reading] rule serves both")
    last = int(reading["last_reads"])
    margins = {k: Fraction(str(reading[k])) for k in exploit.READING_MARGINS}
    pilots, run0s, guards, strikes = {}, {}, {}, {}
    for pair in PAIRS:
        g3, g2 = gates[("route3", pair)], gates[("route2", pair)]
        pair_gates(g3, VARIANTS["route3"][pair], g2, VARIANTS["route2"][pair], pair)
        for arm in ARMS:
            g, v, mm = gates[(arm, pair)], VARIANTS[arm][pair], m[arm][pair]
            stage = f"LS1.4 {arm} {pair}"
            under = gates[PILOT_RAN_UNDER.get((arm, pair), (arm, pair))]
            pilots[(arm, pair)] = read_pilot(mm, arm, pair, g, under, f"{stage} pilot")
            run0s[(arm, pair)] = read_run0(mm, arm, pair, g, v, last, f"{stage} run 0")
            guards[(arm, pair)] = read_run(mm, "guard", arm, pair, g, v, "guard", last, f"{stage} Guard run")
            if "strike" in mm:
                strikes[(arm, pair)] = read_run(mm, "strike", arm, pair, g, v, "strike", last,
                                                f"{stage} Strike run of record")
        pair_run0(run0s[("route3", pair)], run0s[("route2", pair)], pair)
    strike_pairs = {p: {a: run0s[(a, p)] for a in ARMS} for p in PAIRS}
    guard_pairs = {p: {a: guards[(a, p)] for a in ARMS} for p in PAIRS}
    out_strike = {"what": "Strike team: the run 0 cell (reaches against the parked Guard, the reference's first "
                          f"starts), each pair's score the mean of its run 0's last {last} reads",
                  **verdict("strike", strike_pairs, margins),
                  "pairs": {p: {a: scored(strike_pairs[p][a]) for a in ARMS} for p in PAIRS}}
    out_guard = {"what": "Guard team: the pooled row of the final INFO batch (every script of the pool, the reference "
                         "starts), paired start by start",
                 **verdict("guard", guard_pairs, margins), "pairs": {}}
    for p in PAIRS:
        g3, g2 = guards[("route3", p)], guards[("route2", p)]
        out_guard["pairs"][p] = {**{a: scored(guard_pairs[p][a]) for a in ARMS},
                                 "paired_difference": pair_runs(g3, g2, "guard", p),
                                 "cells": cell_gaps(g3, g2, margins["margin_cell"])}
    strike_info = {}
    for p in PAIRS:
        given = {a: strikes[(a, p)] for a in ARMS if (a, p) in strikes}
        if not given:
            continue
        entry = {"arms": {a: scored(r) for a, r in given.items()}, "label": "INFO"}
        if len(given) == len(ARMS):
            entry["paired_difference"] = pair_runs(given["route3"], given["route2"], "strike", p)
        strike_info[p] = entry
    runs = {"guard": guards, "strike": strikes}
    info = {"choice_shares": {s: {p: {a: runs[s][(a, p)]["choice_share"] for a in ARMS if (a, p) in runs[s]}
                                  for p in PAIRS if any((a, p) in runs[s] for a in ARMS)} for s in SIDES},
            "best_single_choice": {s: {p: {a: runs[s][(a, p)]["best_single_choice"] for a in ARMS
                                           if (a, p) in runs[s]} for p in PAIRS if any((a, p) in runs[s] for a in ARMS)}
                                   for s in SIDES},
            "strike_runs_of_record": strike_info,
            "choice_share_note": "described, not worded; the late decision bins are survivor-biased"}
    return {"gates": {f"{a} {p}": {"file": rel(gates[(a, p)].path), "sha256": gates[(a, p)].sha256,
                                   "variant": VARIANTS[a][p]} for a in ARMS for p in PAIRS},
            "label": str(gates[(READING_ARM, PAIRS[0])].run["kind"]),
            "reading": dict(reading), "reading_from": rel(gates[(READING_ARM, PAIRS[0])].path),
            "pilots": {f"{a} {p}": pilots[(a, p)] for a in ARMS for p in PAIRS},
            "strike": out_strike, "guard": out_guard, "info": info}


# ------------------------------------------------------------------------------------------------ output
def plain(obj):
    if isinstance(obj, dict):
        return {k: plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [plain(v) for v in obj]
    if isinstance(obj, Fraction):
        return float(obj)
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def render(out: dict) -> str:
    lines = [f"Simulator: tier 1 training simulator; {STATUS}. Label: {out['label']}. {out['review']}", "",
             f"Route 2: {ARM_NAME['route2']}; route 3: {ARM_NAME['route3']}. Pair s1 = variant base (route 2 seed 1), "
             f"pair s2 = route 2 seed 2 (route 3 variant base_s2). The rule is {out['reading_from']} [reading].", ""]
    for side in SIDES:
        sd = out[side]
        lines += [f"## {SIDE_NAME[side]} team: **{sd['word']}**", "", sd["what"] + ".", "",
                  f"Margin {sd['margin_key']} = {sd['margin']}; route 2 mean {sd['mean']['route2']:.4f}, route 3 mean "
                  f"{sd['mean']['route3']:.4f}; no drop needs route 3's mean >= "
                  f"{sd['no_drop_needs']['mean_at_least']:.4f} and each pair >= "
                  f"{sd['no_drop_needs']['each_pair_at_least']:.4f}; below when the mean < "
                  f"{sd['below_when_mean_under']:.4f}." + (f" Next: {sd['next']}." if sd.get("next") else ""), "",
                  "| Pair | Route 2 score | Route 2 lowest read | Route 3 score | Route 3 lowest read | Seeds |",
                  "|---|---|---|---|---|---|"]
        for p in PAIRS:
            a, b = sd["pairs"][p]["route2"], sd["pairs"][p]["route3"]
            lines.append(f"| {p} | {a['score']:.4f} ({a['score_exact']}) | {a['min_last_reads']:.4f} | "
                         f"{b['score']:.4f} ({b['score_exact']}) | {b['min_last_reads']:.4f} | "
                         f"{a['train_seed']} / {b['train_seed']} |")
        lines.append("")
        if side == "guard":
            for p in PAIRS:
                d = sd["pairs"][p]["paired_difference"]
                lines.append(f"- Pair {p}, route 3 minus route 2, paired start by start (INFO): {d['diff']:+.4f} "
                             f"[{d['ci'][0]:+.4f}, {d['ci'][1]:+.4f}], {d['word']}.")
                miss = [c["opponent"] for c in sd["pairs"][p]["cells"] if c["beyond_margin_cell"]]
                lines.append(f"- Pair {p}, cells with route 3 below route 2 by more than margin_cell (INFO, never "
                             f"gated): {', '.join(miss) if miss else 'none'}.")
            lines.append("")
    lines += ["## INFO", ""]
    for p, e in out["info"]["strike_runs_of_record"].items():
        arms = ", ".join(f"{a} pooled {v['score']:.4f}" for a, v in e["arms"].items())
        line = f"- Strike runs of record, pair {p}: {arms}"
        if "paired_difference" in e:
            d = e["paired_difference"]
            line += f"; route 3 minus route 2, start by start: {d['diff']:+.4f} [{d['ci'][0]:+.4f}, {d['ci'][1]:+.4f}]"
        lines.append(line + ".")
    lines += [f"- Best single fixed choice per run: {SCRIPTS_BEST} (read.json).",
              "- Choice shares per opponent, both arms: read.json (described, not worded).", "",
              "## Departure from workflow section 6", "", DEPARTURE, "", "## What it cannot show", ""]
    lines += [f"- {x}" for x in out["cannot_show"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ste_ls1_read.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        if (a.out / "read.json").exists():
            raise Refused(f"{rel(a.out)} already holds read.json: a new read needs a new folder")
        m = tomllib.loads(a.manifest.read_text())
        body = read(m)
    except Refused as err:
        print(f"refused: {err}", file=sys.stderr)
        return EXIT_REFUSED
    out = plain({"what": "STE LS1.4 read: route 3 against route 2, training pair by training pair "
                         "(scripts/ste_ls1_read.py); observed in the training simulator",
                 "status": STATUS, "review": "Draft until two independent reviewers have checked it (R22).",
                 "manifest": rel(a.manifest), "manifest_sha256": exploit.sha256_file(a.manifest), **body,
                 "departure": DEPARTURE, "cannot_show": CANNOT_SHOW})
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "read.json").write_text(json.dumps(out, indent=1, allow_nan=False))
    (a.out / "read.md").write_text(render(out))
    for side in SIDES:
        print(f"{SIDE_NAME[side]} team: {out[side]['word']}")
    return EXIT_DONE


if __name__ == "__main__":
    sys.exit(main())
