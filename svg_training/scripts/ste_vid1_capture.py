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
    ap.add_argument("--record-run-dir", required=True, help="the recorded L0.11 run folder (read only)")
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


def main(argv=None) -> int:
    a = parse(argv)
    settings = load_video_settings(a.settings)
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
