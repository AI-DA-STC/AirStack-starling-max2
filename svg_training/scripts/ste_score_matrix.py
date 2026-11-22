#!/usr/bin/env python
"""STE L1 side track: score one saved player against every script of the other team (INFO; scoring only, no training).

    ste_score_matrix.py --settings configs/ste_l1/score_matrix_<job>.toml --run-dir runs/<date>_ste_<job>
                        --cap-h <GPU-h> [--allow-code-change]

Launch through ``scripts/ste_job.py launch --task <the settings' [job] task> --gpu-h <H> ... -- <this command> --cap-h
<H>`` (the same H: a run folder whose job.json asks for other hours, or a GPU job on the CPU, is refused). Tier 1;
results are "observed in the training simulator". Spec: ste_learning/drafts/L1_SIDE_TRACK_SPEC.md v2 (item 5): used by
L1.12 (T46's base Guard team against the 6 Strike scripts), T52's re-score at 30 s and 120 s, and the L1.13 arms'
re-score at the other clock.

The player is a run folder of ``scripts/ste_exploit_l012.py`` (agent_final.pt, its gates.toml, eval_final.npz; as the
folders in ste_provisional/players/). What it does, in order (every pin in the settings file):
1. checks every pinned file by sha256 before anything plays (the player's gates.toml, agent_final.pt, hashed before it
   is loaded, and eval_final.npz; the player's own game and reference files as its gate file pins them; each scoring
   game file and its reference, whose start set must be the player's). A FILL_ value, a missing file or a mismatch:
   exit 2, nothing played;
2. control ``own_replay``: the player's whole evaluation batch replayed (its cells, its own game and starts, the network
   rebuilt by ``exploit_train.team_from_modules``) equal to its eval_final.npz game for game (exact keys; closest
   approach within the L0.11 same_seed_closest_tol_m on CUDA, 0 on the CPU) and its trained cell's wins = ``own_wins``
   (T46's Guard 913, T52's 103): ``scoring.check_replay_batch``, as L0.12d's C1/C2;
3. per scoring game, one batch per script x of the other team: the player against x, then every script of the player's
   team against x, on the reference's starts. Control ``scripts_<game>_<x>``: every script cell equal to the reference
   game for game (exploit.replay_ok's exact rule on any device; the reference's own clock, so a script game that a
   shorter clock would cut makes it fail), with the batch's paired starts, one for one and non-finite checks; on the
   player's own game, the player's cell against its own training opponent must also equal own_replay's trained cell
   game for game (key ``own_cell``; fix round 1);
4. only when every control is PASS: results.json / results.md: per scoring game, one row per script x, WORST CELL FIRST
   (the player's fewest wins), the player's wins with Wilson 95 % intervals, the best script of the player's team
   against x on the same starts (exploit.best_script, the L0.11 tie rule) and the paired counts against it, how the games
   ended (``scoring.end_reasons``) and the median game length. No clips (scoring only: the runs hold theirs).

Every batch's per-game record is kept in ``games/`` as soon as it is played (also when its control fails); no number is
summarised unless every control passes. The run contract (``ste/run_contract.py``): the same command resumes at the
next batch not yet checked; SIGINT or SIGTERM stops before the next tick (exit 4); the cap is effective seconds =
--cap-h x 3600 (exit 3). Exit codes: 0 done; 2 refused; 3 cap; 4 stopped on request; 5 a non-finite action; 6
CONTROL_FAILED (terminal: the same command on the same folder ends with 6 again)."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import tomllib
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import torch  # noqa: E402

import ste_exploit_l012 as l012  # noqa: E402  (the simulator words, the machine line)
import ste_sweep_l011 as l011  # noqa: E402  (code pinning, JSON writing)
from svg_training.core.rewards import RUNNING  # noqa: E402
from svg_training.ste import atomic, exploit, exploit_train, scoring, sweep  # noqa: E402
from svg_training.ste.run_contract import (EXIT_CONTROL_FAILED, EXIT_DONE, EXIT_FOR_STOP, EXIT_NONFINITE,  # noqa: E402
                                           EXIT_REFUSED, STOP_CAP, RunBusyError, RunGuard)
from svg_training.viz import replay3d as r3  # noqa: E402

SETTINGS_COPY, PINNED_SHA = "score_matrix.toml", "settings.sha256"
CONTROLS_FILE, RESULTS, GAMES = "controls.json", "results.json", "games"
HOUR_S = 3600.0
PASS = scoring.PASS
PLAYER = "trained"                 # the saved player's name in a matrix cell
OWN = "own_replay"                 # the control: the player's own evaluation batch replayed
OWN_BATCH = "own_replay"
SIDES = exploit.SIDES
SIMULATOR = l012.SIMULATOR
OBSERVED = "observed in the training simulator"
LIMITS = "one trained network, one start set; " + OBSERVED
TOL_SOURCE = "configs/ste_l011/gates.toml"   # the L0.11 gate file: same_seed_closest_tol_m (sweep.GATES_FILE)
_KEYS = {
    "job": {"task", "what", "kind"},
    "player": {"label", "dir", "side", "variant", "gates_sha256", "agent_sha256", "eval_sha256", "own_wins",
               "own_source"},
    "games": {"name", "file", "sha256", "reference", "reference_sha256", "reference_variant", "clock_label"},
}


def say(text: str) -> None:
    print(f"[score] {text}", flush=True)


def refuse(text: str) -> int:
    print(f"refused: {text}", file=sys.stderr, flush=True)
    return EXIT_REFUSED


def parse(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--settings", type=Path, required=True)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--cap-h", type=float, required=True, help="cap in effective hours (= the launcher's --gpu-h)")
    ap.add_argument("--allow-code-change", action="store_true",
                    help="resume although the code differs from the first launch's (recorded in code.json)")
    return ap.parse_args(argv)


def load_settings(path: Path) -> dict:
    """The settings file: [job], [player] and one or more [[games]], each with exactly its keys (ValueError names an
    unknown or missing key, a bad side or game name, or a value still marked FILL_)."""
    data = tomllib.loads(Path(path).read_text())
    unknown = sorted(set(data) - set(_KEYS))
    if unknown:
        raise ValueError(f"unknown section(s) in {Path(path).name}: {unknown}")
    exploit._exact(data.get("job"), _KEYS["job"], "job")
    exploit._exact(data.get("player"), _KEYS["player"], "player")
    games = data.get("games")
    if not isinstance(games, list) or not games:
        raise ValueError("[[games]]: at least one scoring game")
    for g in games:
        exploit._exact(g, _KEYS["games"], "games")
    names = [g["name"] for g in games]
    if len(set(names)) != len(names) or any(not n.replace("_", "").isalnum() for n in names):
        raise ValueError(f"[[games]] names must be distinct letters, digits and '_': {names}")
    if data["player"]["side"] not in SIDES:
        raise ValueError(f"player.side must be one of {SIDES}")
    todo = [f"[{s}] {k}" for s, t in (("job", data["job"]), ("player", data["player"])) for k, v in t.items()
            if isinstance(v, str) and v.startswith(exploit.FILL_MARK)]
    todo += [f"[[games]] {g['name']} {k}" for g in games for k, v in g.items()
             if isinstance(v, str) and v.startswith(exploit.FILL_MARK)]
    if todo:
        raise ValueError(f"not filled yet: {', '.join(todo)} (fill them from the player's finished run folder)")
    return data


def _path(text: str) -> Path:
    p = Path(text)
    return p if p.is_absolute() else ROOT / p


def _reference(path: Path, want: str, what: str):
    why = scoring.sha_problem(path, want, what)
    if why:
        return None, why
    return exploit.load_reference(path), None


# ================================================================================================ cells
def matrix_cells(player_gates: exploit.ExploitGates, side: str, x: str) -> list:
    """One batch (Guard, Strike): the player against script ``x`` of the other team, then every script of the player's
    team against ``x``."""
    mine = player_gates.players["strikes" if side == "strike" else "guards"]
    names = [PLAYER, *mine]
    return [(x, m) if side == "strike" else (m, x) for m in names]


def is_script(cell: tuple) -> bool:
    return PLAYER not in cell


def batch_name(game: str, x: str) -> str:
    return f"{game}__{x}"


# ================================================================================================ the inputs
def check_inputs(a: argparse.Namespace, s: dict):
    """(the loaded inputs, None) or (None, the reason to refuse). Nothing is played here; the network file is hashed
    before it is loaded."""
    p = s["player"]
    pdir = _path(p["dir"])
    for name, key in (("gates.toml", "gates_sha256"), ("agent_final.pt", "agent_sha256"), ("eval_final.npz", "eval_sha256")):
        why = scoring.sha_problem(pdir / name, p[key], f"the player's {name}")
        if why:
            return None, why
    try:
        pg_gates = exploit.load_gates(pdir / "gates.toml")
    except (OSError, ValueError) as err:
        return None, f"the player's gate file: {err}"
    variant, side = p["variant"], p["side"]
    if variant not in pg_gates.variants:
        return None, f"variant {variant!r} is not in the player's gate file ({list(pg_gates.variants)})"
    problems = exploit.game_file_problems(pg_gates)
    if problems:
        return None, "the player's game file(s) differ from its gate file: " + "; ".join(problems)
    own_ref, why = _reference(ROOT / pg_gates.reference["file"], pg_gates.reference["sha256"], "the player's reference")
    if why:
        return None, why
    if own_ref.start_sha256 != pg_gates.reference["start_sha256"]:
        return None, f"the player's reference starts sha256 {own_ref.start_sha256}, its gate file pins " \
                     f"{pg_gates.reference['start_sha256']}"
    device, n = str(pg_gates.run["device"]), int(pg_gates.run["eval_games"])
    if device.startswith("cuda") and not torch.cuda.is_available():
        return None, "the player's gate file plays on cuda and PyTorch sees no GPU"
    if not (a.cap_h > 0 and a.cap_h < float("inf")):
        return None, f"--cap-h must be a finite number of hours above 0, got {a.cap_h!r}"
    job_file = a.run_dir / "job.json"
    if job_file.is_file():
        gpu_h = float(json.loads(job_file.read_text()).get("gpu_h", 0))
        if gpu_h > 0 and abs(gpu_h - a.cap_h) > 1e-9:
            return None, f"the launcher asked for {gpu_h} GPU-h, --cap-h is {a.cap_h}: keep the two equal"
        if (gpu_h > 0) != device.startswith("cuda"):
            return None, f"the launcher asked for {gpu_h} GPU-h and the player's gate file plays on {device!r}"
    own_cells = exploit.eval_cells(pg_gates, variant, side)
    if exploit.EXPLOITER not in own_cells[0]:
        return None, f"cell 0 of the player's evaluation batch is {own_cells[0]}, not the trained team"
    with np.load(pdir / "eval_final.npz") as d:
        record = {k: d[k] for k in r3.EXACT_KEYS + r3.CLOSE_KEYS if k in d.files}
    if len(record["outcome"]) != len(own_cells) * n:
        return None, f"the player's eval_final.npz holds {len(record['outcome'])} games, its batch {len(own_cells)} " \
                     f"cells x {n}"
    others = pg_gates.players["guards" if side == "strike" else "strikes"]
    games = []
    for g in s["games"]:
        why = scoring.sha_problem(_path(g["file"]), g["sha256"], f"scoring game {g['name']}'s file")
        if why:
            return None, why
        ref, why = _reference(_path(g["reference"]), g["reference_sha256"], f"scoring game {g['name']}'s reference")
        if why:
            return None, why
        if ref.start_sha256 != own_ref.start_sha256:
            return None, f"scoring game {g['name']}'s reference holds another start set than the player's (not paired)"
        missing = [c for x in others for c in matrix_cells(pg_gates, side, x)
                   if is_script(c) and (g["reference_variant"], *c) not in ref.cells]
        if missing:
            return None, f"scoring game {g['name']}'s reference has no cell {missing[:3]} (variant " \
                         f"{g['reference_variant']!r})"
        cfg = exploit.load_game_cfg_file(_path(g["file"]))
        own_game = g["sha256"] == pg_gates.games[pg_gates.variants[variant]["game"]].sha256    # the player's own game
        games.append(SimpleNamespace(name=g["name"], cfg=cfg, ref=ref, rv=g["reference_variant"], spec=g, own=own_game))
    modules = torch.load(pdir / "agent_final.pt", map_location=device, weights_only=False)
    team = exploit_train.team_from_modules(side, modules, list(pg_gates.trainer["hidden"]), device)
    team.name = PLAYER
    return SimpleNamespace(pdir=pdir, gates=pg_gates, variant=variant, side=side, own_cfg=exploit.variant_cfg(pg_gates, variant),
                           own_ref=own_ref, own_cells=own_cells, record=record, device=device, n=n,
                           ticks=int(pg_gates.run["ticks_cap"]), hold=int(pg_gates.trainer["decision_ticks"]),
                           size=pg_gates.run["size"], others=list(others), games=games, team=team,
                           own_opponent=exploit.opponent_of(pg_gates, variant, side)), None


def play_matrix_batch(cfg, size, ref, cells, n, device, seed, ticks, x: str, **kw) -> dict:
    """One matrix batch (the player and its team's scripts against script ``x``): ``exploit.play_cells``."""
    return exploit.play_cells(cfg, size, ref, cells, n, device, seed, ticks, **kw)


def check_own_cell(pg: dict, own_pg: dict, n: int, tol: float) -> dict:
    """Fix round 1: on the player's own game, its cell against its own training opponent (cell 0 of the batch) is the
    same games as own_replay's trained cell (cell 0): equal game for game (exact keys, closest approach within
    ``tol``; ``viz/replay3d.check_against_record``)."""
    check = r3.check_against_record(exploit.slice_cell(pg, 0, n), exploit.slice_cell(own_pg, 0, n), tol_m=tol)
    return {"equal": bool(check["equal"]), "mismatches": check["mismatches"]}


# ================================================================================================ results
def row_of(ctx, game, x: str, pg: dict) -> dict:
    """One script x of one scoring game: the player's wins (Wilson 95 %), the best script of its team against x on the
    same starts with the paired counts, how the games ended, the median game length."""
    cells = matrix_cells(ctx.gates, ctx.side, x)
    n, side = ctx.n, ctx.side
    mine = exploit.slice_cell(pg, 0, n)
    k, m = scoring.win_count(mine, side)
    scripts = [c for c in cells if is_script(c)]
    per = {c: exploit.slice_cell(pg, cells.index(c), n) for c in scripts}
    best = exploit.best_script(per, side, scripts)
    b_pg = per[best["cell"]]
    finished = not (mine["outcome"] == RUNNING).any() and not (b_pg["outcome"] == RUNNING).any()
    paired = scoring.paired_wins(mine["outcome"], b_pg["outcome"], side) if finished else \
        {"trained_only": None, "script_only": None, "both": None, "neither": None, "sign_test_p": None,
         "note": "unfinished games: no paired counts"}
    ticks = int(pg["game_ticks"])
    return {"opponent": x, "label": exploit.label(ctx.gates, x), "cell": list(cells[0]), **scoring.rate(k, m),
            "unfinished": int(np.sum(mine["outcome"] == RUNNING)), "end_reasons": scoring.end_reasons(mine, ticks),
            "length_median_s": scoring.length_median_s(mine),
            "best_script": {"cell": list(best["cell"]), "name": best["cell"][1 if side == "strike" else 0],
                            **scoring.rate(best["k"], best["n"]), "end_reasons": scoring.end_reasons(b_pg, ticks),
                            "length_median_s": scoring.length_median_s(b_pg)},
            "paired": paired, "game_ticks": ticks}


def reading(ctx, label: str, row: dict) -> str:
    won = "holds" if ctx.side == "guard" else "reaches"
    team = "Guard" if ctx.side == "guard" else "Strike"
    return (f"{label} {won} {row['k']:,} of {row['n']:,} ({row['ci'][0]:.3f}-{row['ci'][1]:.3f}) against {row['label']} "
            f"(best {team} script {row['best_script']['name']}: {row['best_script']['k']:,})")


def results_of(ctx, a, s: dict, pgs: dict, controls: dict, guard: RunGuard, tol: float) -> dict:
    out_games = {}
    for game in ctx.games:
        rows = [row_of(ctx, game, x, pgs[batch_name(game.name, x)]) for x in ctx.others]
        rows.sort(key=lambda r: (r["k"], ctx.others.index(r["opponent"])))          # worst cell first
        out_games[game.name] = {"file": game.spec["file"], "sha256": game.spec["sha256"],
                                "clock_label": game.spec["clock_label"],
                                "game_ticks": rows[0]["game_ticks"] if rows else None,
                                "reference": {"file": game.spec["reference"], "sha256": game.spec["reference_sha256"],
                                              "variant": game.rv},
                                "rows": rows, "readings": [reading(ctx, s["player"]["label"], r) for r in rows]}
    machine = l012.machine()
    return {"what": f"STE {s['job']['task']}: {s['job']['what']}; {OBSERVED}", "task": s["job"]["task"],
            "kind": s["job"]["kind"], "simulator": SIMULATOR, "limits": LIMITS, "controls_pass": True,
            "controls": controls, "player": {**s["player"], "trained_on": ctx.variant,
                                             "opponent": exploit.opponent_of(ctx.gates, ctx.variant, ctx.side),
                                             "opponent_choice": exploit.opponent_choice(ctx.gates, ctx.variant, ctx.side),
                                             "decision_ticks": ctx.hold},
            "games": out_games, "device": ctx.device, "eval_games": ctx.n, "ticks_cap": ctx.ticks,
            "start_sha256": ctx.own_ref.start_sha256, "seed": int(ctx.own_ref.meta["seed"]),
            "closest_tol": {"tol_m": tol, "rule": "0 on the CPU; same_seed_closest_tol_m on CUDA", "source": TOL_SOURCE,
                            "sha256": exploit.sha256_file(ROOT / TOL_SOURCE)},
            "batch_seconds": {k: v.get("seconds") for k, v in controls.items()},
            "effective_s": guard.effective_s(), "cap_h": a.cap_h, "machine": machine, "gpu": machine["gpu"],
            "code": json.loads((a.run_dir / l011.CODE_FILE).read_text()),
            "settings_sha256": exploit.sha256_file(a.settings), "clips": "none: scoring only (the runs hold theirs)"}


def _num(x, fmt: str = "{:.3f}") -> str:
    return "-" if x is None or (isinstance(x, float) and x != x) else fmt.format(x)


def write_md(run_dir: Path, s: dict, controls: dict, result: dict | None) -> None:
    lines = [f"Simulator: {SIMULATOR}. {OBSERVED.capitalize()}; nothing here is a flight result.", "",
             f"# {s['job']['task']}: {s['job']['what']} (INFO)", "",
             "## Controls (read these first; any control not PASS: no number is reported)", "",
             "| Control | Status | Detail |", "|---|---|---|"]
    lines += [f"| {k} | **{v['status']}** | {v['detail']} |" for k, v in controls.items()]
    if result is not None:
        won = "holds" if result["player"]["side"] == "guard" else "reaches"
        for name, g in result["games"].items():
            lines += ["", f"## {name}: `{g['file']}` ({g['clock_label']}; {LIMITS}), worst cell first", "",
                      f"| Opponent | Player's {won} (Wilson 95 %) | Best script, same starts | Paired: player only / "
                      f"script only / both / neither | Player's games: reach / all Strike tagged / clock / other hold / "
                      f"unfinished | Median length (s) |", "|---|---|---|---|---|---|"]
            for r in g["rows"]:
                b, p, e = r["best_script"], r["paired"], r["end_reasons"]
                lines.append(f"| {r['label']} | {r['k']}/{r['n']} ({_num(r['ci'][0])}-{_num(r['ci'][1])}) | "
                             f"{b['name']} {b['k']}/{b['n']} ({_num(b['ci'][0])}-{_num(b['ci'][1])}) | "
                             f"{p['trained_only']} / {p['script_only']} / {p['both']} / {p['neither']} | "
                             f"{e['reach']} / {e['all_strikes_tagged']} / {e['clock']} / {e['other_hold']} / "
                             f"{e['unfinished']} | {_num(r['length_median_s'], '{:.1f}')} |")
            lines += ["", "Reading:", ""] + [f"- {x}." for x in g["readings"]]
    atomic.write_text(run_dir / "results.md", "\n".join(lines) + "\n")


# ================================================================================================ the run
def run(ctx, a: argparse.Namespace, s: dict, guard: RunGuard) -> int:
    """The player's own replay, then one batch per scoring game and script of the other team; each batch's npz as soon
    as it is played; results only when every control PASS."""
    run_dir = a.run_dir
    (run_dir / GAMES).mkdir(exist_ok=True)
    controls = json.loads((run_dir / CONTROLS_FILE).read_text()) if (run_dir / CONTROLS_FILE).is_file() else {}
    every, seen = int(ctx.gates.run["cap_check_every_ticks"]), [0]
    tol = 0.0 if ctx.device == "cpu" else float(sweep.load_gates().controls["same_seed_closest_tol_m"])

    def should_stop() -> bool:
        if guard.stop_requested:
            return True
        seen[0] += 1
        return seen[0] % every == 0 and guard.cap_reached()

    def stopped() -> int:
        guard.save(len(controls), {"done": sorted(controls)})
        reason = guard.stop_reason() or STOP_CAP
        say(f"stopped ({reason}); the same command resumes at the next batch not yet checked")
        return EXIT_FOR_STOP[reason]

    def settle(key: str, ctl: dict) -> int | None:
        controls[key] = ctl
        l011.write_json(run_dir / CONTROLS_FILE, controls)
        say(f"{key} {ctl['status']}: {ctl['detail'][:400]}")
        guard.save(len(controls), {"done": sorted(controls)})
        code = scoring.ending({key: ctl})
        if code is not None:
            write_md(run_dir, s, controls, None)
            say(f"{'NON-FINITE' if code == EXIT_NONFINITE else 'CONTROL FAILED'}: no number is reported (exit {code}); "
                f"the batch's per-game record is kept in {GAMES}/ for diagnosis")
        return code

    expected = int(s["player"]["own_wins"])
    batches = [(OWN, OWN_BATCH, ctx.own_cfg, ctx.own_ref, ctx.own_cells, {"learner": ctx.team}, None,
                lambda pg: scoring.check_replay_batch(pg, ctx.record, ctx.own_ref, ctx.n, ctx.side, expected, tol))]
    for game in ctx.games:
        for x in ctx.others:
            cells = matrix_cells(ctx.gates, ctx.side, x)
            batches.append((f"scripts_{batch_name(game.name, x)}", batch_name(game.name, x), game.cfg, game.ref, cells,
                            {"players": {PLAYER: ctx.team}}, (game, x),
                            lambda pg, c=cells, g=game: scoring.check_script_cells(pg, c, g.ref, g.rv, ctx.n, ctx.ticks,
                                                                                    is_script, phase="matrix")))
    pgs, own_pg = {}, None
    for key, name, cfg, ref, cells, players, gx, check in batches:
        path = run_dir / GAMES / f"{name}.npz"
        if controls.get(key, {}).get("status") == PASS and path.is_file():
            if name != OWN_BATCH:
                pgs[name] = scoring.load_batch(path)
            else:
                own_pg = scoring.load_batch(path)
            continue
        started = time.perf_counter()
        say(f"{key}: batch {name}, {len(cells)} cells x {ctx.n} on {ctx.device}")
        try:
            if gx is None:
                pg = exploit.play_cells(cfg, ctx.size, ref, cells, ctx.n, ctx.device, int(ref.meta["seed"]), ctx.ticks,
                                        hold_ticks=ctx.hold, should_stop=should_stop, **players)
            else:
                pg = play_matrix_batch(cfg, ctx.size, ref, cells, ctx.n, ctx.device, int(ref.meta["seed"]), ctx.ticks,
                                       x=gx[1], hold_ticks=ctx.hold, should_stop=should_stop, **players)
        except sweep.SweepStopped:
            return stopped()
        took = time.perf_counter() - started
        scoring.save_batch(path, pg)                                # kept for diagnosis even when the control fails
        l011.write_json(path.with_suffix(".json"), {"cells": [list(c) for c in cells], "games_per_cell": ctx.n})
        ctl = check(pg)
        if gx is not None and gx[0].own and gx[1] == ctx.own_opponent:
            # the player's own game and own training opponent: the same games as own_replay's trained cell
            own = check_own_cell(pg, own_pg, ctx.n, tol)
            ctl["own_cell"] = own
            ctl["detail"] += (f"; the player's cell v its own training opponent {'EQUALS' if own['equal'] else 'DIFFERS FROM'}"
                              f" own_replay's trained cell game for game {own['mismatches']}")
            if not own["equal"] and ctl["status"] == PASS:
                ctl["status"] = scoring.FAIL
        code = settle(key, {**ctl, "seconds": took})
        if code is not None:
            return code
        if name != OWN_BATCH:
            pgs[name] = pg
        else:
            own_pg = pg
    want = {b[0] for b in batches}
    if set(controls) != want or {v["status"] for v in controls.values()} != {PASS}:
        write_md(run_dir, s, controls, None)
        return EXIT_CONTROL_FAILED
    result = results_of(ctx, a, s, pgs, controls, guard, tol)
    result["complete"] = True                                       # written last
    l011.write_json(run_dir / RESULTS, result)
    write_md(run_dir, s, controls, result)
    guard.save(len(controls), {"done": sorted(controls), "phase": "done"})
    for g in result["games"].values():
        for line in g["readings"]:
            say(line)
    say(f"done: {run_dir / 'results.md'}")
    return EXIT_DONE


def main(argv: list[str] | None = None) -> int:
    a = parse(list(sys.argv[1:] if argv is None else argv))
    try:
        s = load_settings(a.settings)
    except (OSError, ValueError) as err:
        return refuse(f"settings {a.settings}: {err}")
    pinned = a.run_dir / PINNED_SHA
    sha = exploit.sha256_file(a.settings)
    if pinned.is_file() and pinned.read_text().strip() != sha:
        return refuse(f"the settings changed since the first launch in {a.run_dir} (pinned {pinned.read_text().strip()}, "
                      f"now {sha}): a new pin means a new run folder")
    controls_file = a.run_dir / CONTROLS_FILE
    if controls_file.is_file():
        code = scoring.ending(json.loads(controls_file.read_text()))
        if code is not None:
            print(f"a control is not PASS in this run folder ({controls_file}): read it; a new run needs a new run folder "
                  f"(exit {code})", file=sys.stderr, flush=True)
            return code
    res = a.run_dir / RESULTS
    if res.is_file() and json.loads(res.read_text()).get("complete") is True:
        say(f"this run folder is done ({res}); nothing to do")
        return EXIT_DONE
    ctx, why = check_inputs(a, s)
    if why:
        return refuse(why)
    a.run_dir.mkdir(parents=True, exist_ok=True)
    try:
        with RunGuard(a.run_dir, cap_s=a.cap_h * HOUR_S) as guard:
            changed = l011.pin_code(a)
            if changed:
                return refuse(changed)
            if not pinned.is_file():
                shutil.copyfile(a.settings, a.run_dir / SETTINGS_COPY)
                atomic.write_text(pinned, sha + "\n")
            guard.load_latest()
            return run(ctx, a, s, guard)
    except RunBusyError as err:
        return refuse(str(err))


if __name__ == "__main__":
    sys.exit(main())
