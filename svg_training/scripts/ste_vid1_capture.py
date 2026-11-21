#!/usr/bin/env python3
"""VID-1 part 2, step 1: play the key games of a recorded L0.11 screen again, step by step, and check they are the games
in the record (tier 1; no Isaac).

    unset PYTHONPATH
    PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/ste_vid1_capture.py \\
        --record-run-dir <T44 run folder> --out runs/<date>_ste_vid1 [--variants base tag_1p2 tag_1p4]

For each variant of ``configs/ste_video.toml [key_games]``: g* and s* from the run's ``results.json`` (its shortlist
table), the cell's batch from the run's own copy of the gate file (its sha256 must be the one in the settings), the key
games by the settings' rule from the run's stored outcomes (``cells/<batch>.npz``), then the whole batch played again
on the record's device (``viz/replay3d.capture_batch``: the batch-mates matter, the filter's early stop is batch-wide).
Every game of the batch must equal the record on outcome, end step, tags, Strike drones left and start positions,
and agree on the closest approach within the gate file's same-seed tolerance (0 on the CPU); a variant's older
trajectories are deleted before it is played, and only then are the trajectories written (``<out>/trajectories/<variant>_<outcome>.npz`` + ``.json``), with
``<out>/capture.json`` (the check, per variant). Visual tooling: no gates, no record, no ledger row.

**Trained players (VID-1b)**, ``--trained-runs-dir <folder holding the L0.12 run folders>``: for each run of
``[trained_games] runs``: the run's gate file (sha256 pinned), its ``run.json`` (variant, side) and ``agent_final.pt``;
the run's evaluation batch played again on its device (``viz/replay3d.capture_trained``: T44's starts, every cell, the
trained team held 0.6 s, mean actions); the key game = the lowest game index of the exploiter cell that the trained team
won in the run's own ``eval_final.npz``. It is drawn only if the replayed game equals that record game (outcome, end
step, tags, Strike drones left, start positions; closest approach within the L0.11 gate file's same-seed tolerance); the
whole batch's agreement is reported. Writes ``<out>/trajectories/l012_<variant>_<side>.npz`` + ``.json``.

Exit codes: 0 done; 1 a replayed batch differs from the record (nothing drawn from it); 2 refused (bad input: gate file
sha256, a changed game file, a missing file).
``--games-per-cell`` / ``--ticks-cap`` / ``--device`` overrides exist for the CPU test on a small fake record only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

from svg_training.ste import sweep  # noqa: E402
from svg_training.viz import replay3d as r3  # noqa: E402
from svg_training.viz.starling_look import SETTINGS_FILE, load_video_settings  # noqa: E402


def parse(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--record-run-dir", default=None, help="the recorded L0.11 run folder (read only)")
    ap.add_argument("--trained-runs-dir", default=None,
                    help="VID-1b: the folder holding the L0.12 run folders of [trained_games] runs (read only)")
    ap.add_argument("--runs", nargs="*", default=None, help="VID-1b: default the settings' [trained_games] runs")
    ap.add_argument("--recorded-device", default=None,
                    help="VID-1b, test only: the device the fake record was evaluated on (default: the gate file's)")
    ap.add_argument("--out", required=True, help="output folder (runs/..., git-ignored)")
    ap.add_argument("--settings", default=str(SETTINGS_FILE))
    ap.add_argument("--variants", nargs="*", default=None, help="default: the settings' [key_games] variants")
    ap.add_argument("--device", default=None, help="default: the record's device (the gate file's [run] device)")
    ap.add_argument("--games-per-cell", type=int, default=None, help="test only (a small fake record)")
    ap.add_argument("--ticks-cap", type=int, default=None, help="test only")
    return ap.parse_args(argv)


def say(s: str) -> None:
    print(s, flush=True)


def git_commit() -> str:
    r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


def trained_main(a, settings: dict) -> int:
    """VID-1b: the key games of the trained L0.12 players (module docstring)."""
    import torch

    from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
    from svg_training.ste import exploit, exploit_train

    tg = settings["trained_games"]
    root, out = Path(a.trained_runs_dir), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {"record": tg["record"], "runs_dir": str(root), "commit": git_commit(), "runs": {},
              "rule": "lowest game index of the exploiter cell that the trained team won in eval_final.npz"}
    code = 0
    for name in (a.runs if a.runs is not None else tg["runs"]):
        rd = root / name
        for p in (rd / "gates.toml", rd / "run.json", rd / "agent_final.pt", rd / "eval_final.npz"):
            if not p.is_file():
                say(f"refused: {p} missing")
                return 2
        gates = exploit.load_gates(rd / "gates.toml")
        if gates.sha256 != tg["gates_sha256"]:
            say(f"refused: {name}: gate file sha256 {gates.sha256}, the settings pin {tg['gates_sha256']}")
            return 2
        problems = exploit.game_file_problems(gates)
        if problems:
            say(f"refused: {name}: " + "; ".join(problems))
            return 2
        meta = json.loads((rd / "run.json").read_text())
        variant, side = meta["variant"], meta["side"]
        for stale in (out / "trajectories").glob(f"l012_{variant}_{side}*"):
            stale.unlink()
        ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
        cfg = exploit.variant_cfg(gates, variant)
        cells = exploit.eval_cells(gates, variant, side)
        if exploit.EXPLOITER not in cells[0]:
            say(f"refused: {name}: cell 0 of the evaluation batch is {cells[0]}, not the trained team (the key game "
                f"is taken from cell 0)")
            return 2
        n = int(a.games_per_cell or gates.run["eval_games"])
        ticks = int(a.ticks_cap or gates.run["ticks_cap"])
        device = a.device or gates.run["device"]
        recorded = a.recorded_device or gates.run["device"]
        if str(device) != str(recorded):
            say(f"refused: {name}: the evaluation ran on {recorded}; a replay on {device} cannot be checked against it "
                f"game for game (a CPU replay does not reproduce a CUDA run)")
            return 2
        hold = int(gates.trainer["decision_ticks"])
        with np.load(rd / "eval_final.npz") as d:
            record = {k: d[k] for k in r3.EXACT_KEYS + r3.CLOSE_KEYS if k in d.files}
        want = STRIKE_WIN if side == "strike" else GUARD_WIN
        won = np.flatnonzero(record["outcome"][:n] == want)
        row = {"variant": variant, "side": side, "opponent": exploit.opponent_of(gates, variant, side),
               "cell_counts": r3.cell_counts(record["outcome"][:n]), "game_index": int(won[0]) if won.size else None,
               "files": []}
        if not won.size:
            say(f"{name}: the trained team won no game of its cell: nothing to draw")
            report["runs"][name] = row
            continue
        g = int(won[0])
        modules = torch.load(rd / "agent_final.pt", map_location=device, weights_only=False)
        team = exploit_train.team_from_modules(side, modules, list(gates.trainer["hidden"]), device)
        started = time.time()
        say(f"{name}: {variant} {side}, game {g} of the exploiter cell; playing {len(cells) * n} games on {device}")
        try:
            cap = r3.capture_trained(cfg, gates.run["size"], ref, cells, n, device, int(ref.meta["seed"]), ticks,
                                     team, hold, [g])
        except ValueError as err:
            say(f"refused: {name}: {err}")
            return 2
        # the L0.12 gate file has no closest-approach tolerance: the L0.11 one (same game code, same GPU) is used
        tol = 0.0 if str(device) == "cpu" else float(sweep.load_gates().controls["same_seed_closest_tol_m"])
        game_check = r3.check_against_record({k: v[g:g + 1] for k, v in cap.per_game.items()},
                                             {k: v[g:g + 1] for k, v in record.items()}, tol_m=tol)
        batch_check = r3.check_against_record(cap.per_game, record, tol_m=tol)
        row.update({"game_check": game_check, "batch_check": batch_check, "games_compared": int(len(cells) * n),
                    "seconds": round(time.time() - started, 1)})
        say(f"  game {g}: {'EQUAL' if game_check['equal'] else 'DIFFERENT'} {game_check['mismatches']}; batch "
            f"mismatches {batch_check['mismatches']} ({row['seconds']} s)")
        if not (game_check["equal"] and batch_check["equal"]):      # any game of the batch: exact keys, closest in tol
            code = 1
            report["runs"][name] = row
            continue
        t = cap.trajectories[0]
        t.meta.update({"kind": "trained", "variant": variant, "side": side, "run": name, "record": tg["record"],
                       "guard": row["opponent"] if side == "strike" else "trained Guard team",
                       "strike": row["opponent"] if side == "guard" else "trained Strike team",
                       "outcome_name": "reach" if want == STRIKE_WIN else "hold", "game_index": g,
                       "games_per_cell": n, "cell_index": 0, "cell_counts": row["cell_counts"],
                       "tags": int(record["tags"][g]), "device": str(device), "commit": report["commit"],
                       "gates_sha256": gates.sha256})
        p = r3.save_trajectory(out / "trajectories" / f"l012_{variant}_{side}", t)
        row["files"].append(str(p.relative_to(out)))
        say(f"  -> {p.name}: {t.end_time_s:.2f} s, tags {t.meta['tags']}")
        report["runs"][name] = row
    (out / "capture_trained.json").write_text(json.dumps(report, indent=1))
    say(f"capture_trained.json written; exit {code}")
    return code


def main(argv=None) -> int:
    a = parse(argv)
    settings = load_video_settings(a.settings)
    if a.trained_runs_dir:
        return trained_main(a, settings)
    if not a.record_run_dir:
        say("refused: give --record-run-dir (L0.11 key games) or --trained-runs-dir (L0.12 trained players)")
        return 2
    kg = settings["key_games"]
    rec_dir, out = Path(a.record_run_dir), Path(a.out)
    gates_file = rec_dir / "gates.toml"
    for p in (gates_file, rec_dir / "results.json"):
        if not p.is_file():
            say(f"refused: {p} missing")
            return 2
    gates = sweep.load_gates(gates_file)
    if gates.sha256 != kg["gates_sha256"]:
        say(f"refused: the run's gate file has sha256 {gates.sha256}, the settings pin {kg['gates_sha256']}")
        return 2
    problems = sweep.game_file_problems(gates)
    if problems:
        say("refused: game files changed since the record: " + "; ".join(problems))
        return 2
    results = json.loads((rec_dir / "results.json").read_text())
    stars = {v["variant"]: (v["g_star"], v["s_star"]) for v in results["shortlist"]["variants"]}
    run = dict(gates.run)
    overrides = {}
    for key, val in (("device", a.device), ("games_per_cell", a.games_per_cell), ("ticks_cap", a.ticks_cap)):
        if val is not None:
            run[key] = val
            overrides[key] = val
    plan = sweep.build_plan(gates)
    report = {"record": kg["record"], "record_run_dir": str(rec_dir), "gates_sha256": gates.sha256,
              "rule": f"lowest game index of each outcome {kg['outcomes']} in the g* v s* cell (configs/ste_video.toml)",
              "device": run["device"], "overrides": overrides, "commit": git_commit(), "variants": {}}
    out.mkdir(parents=True, exist_ok=True)
    code = 0
    for variant in (a.variants if a.variants is not None else kg["variants"]):
        cell = stars[variant]
        spec = gates.group(variant)
        game_name, size = sweep.group_game(gates, spec)
        batch_id, cells, ci = r3.find_cell(gates, plan, variant, cell)
        npz = rec_dir / "cells" / (batch_id.replace("/", "__") + ".npz")
        with np.load(npz) as d:
            record = {k: d[k] for k in r3.EXACT_KEYS + r3.CLOSE_KEYS if k in d.files}
        for stale in (out / "trajectories").glob(f"{variant}_*"):     # never leave an older run's game to be drawn
            stale.unlink()
        vrun = dict(run)
        if "ticks_cap" not in overrides:                              # the group's own cap, as the sweep plays it
            vrun["ticks_cap"] = spec.ticks_cap(gates.run)
        tol = 0.0 if str(vrun["device"]) == "cpu" else float(gates.controls["same_seed_closest_tol_m"])
        n = int(run["games_per_cell"])
        picks = r3.pick_key_games(record["outcome"][ci * n:(ci + 1) * n], kg["outcomes"])
        keep = [(name, ci * n + i) for name, i in picks.items() if i is not None]
        cfg = sweep.variant_cfg(gates, game_name)
        started = time.time()
        say(f"{variant}: {cell[0]} v {cell[1]}, batch {batch_id} (cell {ci} of {len(cells)}), key games {picks}; "
            f"playing {len(cells) * n} games on {run['device']}")
        try:
            cap = r3.capture_batch(cfg, size, cells, vrun, [g for _, g in keep],
                                   strike_start_dz_m=spec.strike_start_dz_m or 0)
        except ValueError as err:
            say(f"refused: {variant}: {err}")
            return 2
        check = r3.check_against_record(cap.per_game, record, tol_m=tol)
        row = {"guard": cell[0], "strike": cell[1], "batch": batch_id, "cell_index": ci, "picks": picks,
               "games_compared": int(len(cells) * n), "check": check, "seconds": round(time.time() - started, 1),
               "files": []}
        say(f"  record check: {'EQUAL' if check['equal'] else 'DIFFERENT'} {check['mismatches']} "
            f"({row['seconds']} s)")
        if not check["equal"]:
            code = 1
            report["variants"][variant] = row
            continue
        for (name, g), t in zip(keep, cap.trajectories):
            t.meta.update({"variant": variant, "guard": cell[0], "strike": cell[1], "outcome_name": name,
                           "game_index": int(g - ci * n), "games_per_cell": n, "batch": batch_id, "cell_index": ci,
                           "game": game_name,
                           "size": size, "record": kg["record"], "gates_sha256": gates.sha256,
                           "tags": int(record["tags"][g]), "seed": int(run["seed"]), "device": run["device"],
                           "commit": report["commit"]})
            p = r3.save_trajectory(out / "trajectories" / f"{variant}_{name}", t)
            row["files"].append(str(p.relative_to(out)))
            say(f"  {name}: game {g - ci * n}, {t.end_time_s:.2f} s, tags {record['tags'][g]} -> {p.name}")
        report["variants"][variant] = row
    (out / "capture.json").write_text(json.dumps(report, indent=1))
    say(f"capture.json written; exit {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
