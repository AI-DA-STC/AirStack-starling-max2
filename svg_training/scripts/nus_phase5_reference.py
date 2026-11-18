"""R0: NUS's own hangar self-play lineages converted and scored at our game count, before any Phase 5 gate is used (plan section 4.2,
task M6; frozen table ``[gates.phase5_reference_rebuild]``). CPU or CUDA, conda ``env_isaaclab``:

    cd <svg_training>; unset PYTHONPATH; PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/nus_phase5_reference.py \
        --write-gates                                   # first: verbatim copies of the frozen tables, before any result exists
    ... --check --outputs-dir <NUS outputs/hangar>      # conversion and gate (a) per entry
    ... --score --outputs-dir <NUS outputs/hangar> [--device cuda] [--chunk K]
    ... --run   (check, then score)

Before ``--check``: the reference observations and NUS's JAX actions of every entry (``nus_jax``, CPU):
``scripts/nus_export_reference.py --clone <clone> --archive-entry <entry> ... --seed <S> --episodes-per-half <E>
--out-dir runs/nus_port/phase5/reference/actions`` (E large enough for the gate's observation rows).

1. ``--write-gates`` copies ``[gates.phase5_reference_rebuild]``, ``[gates.phase5_method_match]`` and ``[gates.phase3_converted_policy]``
   of ``configs/nus_port.toml`` verbatim into ``<out>/gates.toml`` and refuses to overwrite it. Every later step reads only that copy.
2. ``--check``: every archive entry of the reference lineages within the gate's generations is converted
   (``nus_convert_checkpoint.py --out-dir <out>/weights``) and checked against gate (a) of ``phase3_converted_policy`` (largest action
   error on at least the gate's observation rows). A failed entry leaves the reference set (``excluded``); more failures than
   ``max_failed_conversions`` stop the stage (exit 1). Writes ``<out>/conversions.json``.
3. ``--score``: every passing Guard entry against every passing Strike entry, plus both APF columns, ``games_per_pairing`` games each on
   one start set drawn once with ``starts_seed`` by the replica's random start rule, both teams deterministic (``nus/crossplay.py``).
   Writes ``<out>/matrix_<games>.json`` and its sha256, the leave-one-out check of 5.1-c (``loo.json``: if any entry misses, 5.1-c is
   INFO), and the reference lineages' 5.1-d seed values (INFO). ``--games-override`` (tests, smoke runs) writes
   ``matrix_<games>_not_of_record.json`` instead and is never the gate's matrix.

Everything is written under runs/ (git-ignored). The script prints counts, verdicts and file hashes, never a partner value. This file
holds no numeric literal other than 0, 1, -1, 2 (G2).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

RUNS_ROOT = ROOT / "runs"   # tests patch it
REFERENCE_DIR = RUNS_ROOT / "nus_port" / "phase5" / "reference"
SOURCE_GATES = ROOT / "configs" / "nus_port.toml"
TABLES = ("phase5_reference_rebuild", "phase5_method_match", "phase3_converted_policy")
TEAM_OF_FOLDER = {"defender": "guard", "attacker": "strike"}
EXIT_STOP = 1


def _under_runs(path: Path) -> Path:
    resolved = Path(path).resolve()
    if RUNS_ROOT.resolve() not in (resolved, *resolved.parents):
        raise SystemExit(f"refusing: {resolved} is outside runs/ (the outputs hold partner values)")
    return resolved


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------------------ gates
def table_text(source: str, table: str) -> str:
    """The verbatim text of ``[gates.<table>]`` up to the next table header."""
    found = re.search(rf"^\[gates\.{re.escape(table)}\]\n.*?(?=^\[|\Z)", source, flags=re.S | re.M)
    if found is None:
        raise SystemExit(f"[gates.{table}] not found in {SOURCE_GATES.name}")
    return found.group(0).rstrip() + "\n"


def write_gates(out: Path, source: Path = SOURCE_GATES) -> Path:
    out = _under_runs(out)
    path = out / "gates.toml"
    if path.exists():
        raise SystemExit(f"refusing: {path} exists (a gates file is never edited after it is written)")
    text = source.read_text()
    body = "\n".join(table_text(text, t) for t in TABLES)
    raw = tomllib.loads(body)["gates"]
    if not all(str(raw[t].get("status", "FROZEN")).startswith("FROZEN") for t in TABLES[:2]):
        raise SystemExit("refusing: the R0 and 5.1 tables are not frozen")
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# R0 gates: verbatim copies of {source.name} (sha256 {_sha256(source)}), written before any R0 result.\n\n{body}")
    return path


def read_gates(out: Path) -> dict:
    path = out / "gates.toml"
    if not path.exists():
        raise SystemExit(f"{path} missing: run --write-gates first")
    return tomllib.loads(path.read_text())["gates"]


# ------------------------------------------------------------------------------------------------ entries
def archive_entries(outputs_dir: Path, runs: list[str], generations: tuple[int, int]) -> list[dict]:
    """Every archive entry of the reference runs inside the generation range, in run and generation order."""
    lo, hi = generations
    out = []
    for run in runs:
        archive = outputs_dir / run / "archive"
        for generation in range(lo, hi + 1):
            found = [p for p in archive.glob(f"{generation:04d}_*") if p.is_dir()]
            if len(found) != 1 or found[0].name.split("_")[-1] not in TEAM_OF_FOLDER:
                raise SystemExit(f"{run}: expected one archive entry for generation {generation}")
            out.append({"lineage": run, "generation": generation, "team": TEAM_OF_FOLDER[found[0].name.split("_")[-1]],
                        "folder": found[0], "name": f"{run}_{found[0].name}"})
    return out


def _load_inputs(args):
    from svg_training.nus.deploy import apply_overrides, load_deploy
    from svg_training.nus.rules import load_rules
    deploy = load_deploy(args.deploy)
    return apply_overrides(load_rules(args.rules), deploy), deploy


def check(args, out: Path, gates: dict) -> dict:
    """Conversion and gate (a) per entry; writes conversions.json."""
    import numpy as np
    import torch

    import nus_convert_checkpoint as convert
    from svg_training.nus.actor import NusActor

    ref, phase3 = gates["phase5_reference_rebuild"], gates["phase3_converted_policy"]
    limit, rows_needed = float(phase3["max_action_error_units_per_step"]), int(phase3["observations_per_team"])
    rules, deploy = _load_inputs(args)
    weights = _under_runs(out / "weights")
    results = []
    for e in archive_entries(args.outputs_dir, list(ref["reference_runs"]), tuple(ref["generations"])):
        row = {k: (str(v) if isinstance(v, Path) else v) for k, v in e.items()}
        try:
            convert.main(["--checkpoint", str(e["folder"]), "--team", e["team"], "--name", e["name"], "--rules", str(args.rules),
                          "--deploy", str(args.deploy), "--out-dir", str(weights)])
            actor = NusActor.load(weights / e["name"], team=e["team"], rules=rules, deploy=deploy)
            data = np.load(args.actions_dir / e["lineage"] / e["folder"].name / f"actions_{e['team']}.npz")
            obs, expected = torch.from_numpy(data["obs"]), torch.from_numpy(data["actions"])
            rows = int(obs.shape[0] * obs.shape[1])
            error = float((actor.act_units(obs) - expected).abs().max())
            row |= {"rows": rows, "max_action_error_units": error, "converted_sha256": actor.meta["sha256"],
                    "pass": bool(rows >= rows_needed and error <= limit),
                    "reason": None if rows >= rows_needed else "fewer observation rows than the gate asks for"}
        except (SystemExit, ValueError, FileNotFoundError, KeyError) as exc:
            row |= {"pass": False, "reason": f"{type(exc).__name__}: {exc}"}
        results.append(row)
        print(f"[gate a] {e['name']}: {'PASS' if row['pass'] else 'FAIL'}", flush=True)
    failed = [r["name"] for r in results if not r["pass"]]
    summary = {"limit_units": limit, "rows_needed": rows_needed, "entries": results, "failed": failed,
               "max_failed_conversions": int(ref["max_failed_conversions"]),
               "stop": len(failed) > int(ref["max_failed_conversions"]), "gates_sha256": _sha256(out / "gates.toml")}
    (out / "conversions.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"[gate a] {len(results) - len(failed)}/{len(results)} entries pass; stop={summary['stop']}", flush=True)
    return summary


def score(args, out: Path, gates: dict) -> dict:
    """The R0 matrix on the replica, the leave-one-out check and the reference 5.1-d seed values."""
    import torch

    from svg_training.nus import crossplay as X
    from svg_training.nus.actor import NusActor
    from svg_training.nus.mappo import tree_from_converted
    from svg_training.nus.method_cfg import load_method
    from svg_training.nus.replica_train import NusTrainEnv

    ref, match = gates["phase5_reference_rebuild"], gates["phase5_method_match"]
    if ref["engine"] != "replica" or ref["action_mode"] != "deterministic" or ref["starts"] != "shared":
        raise SystemExit("this script scores only the replica with shared starts and deterministic actions (the frozen R0 table)")
    conversions = json.loads((out / "conversions.json").read_text())
    if conversions["stop"]:
        raise SystemExit(EXIT_STOP)
    rules, deploy = _load_inputs(args)
    env = NusTrainEnv(rules, deploy, load_method(args.method), device=args.device)
    guards, strikes, settings, excluded = {}, {}, set(), set()
    for row in conversions["entries"]:
        entry = X.Entry(row["lineage"], int(row["generation"]), row["team"])
        if not row["pass"]:
            excluded.add(entry)
            continue
        actor = NusActor.load(out / "weights" / row["name"], team=row["team"], rules=rules, deploy=deploy, device=args.device)
        settings.add((actor.bf16, actor.activation_name, actor.eps, actor.use_norm))
        (guards if row["team"] == "guard" else strikes)[entry] = tree_from_converted(actor._params)
    if len(settings) != 1:
        raise SystemExit("the reference entries do not share one network setting; the stacked scorer needs one")
    bf16, activation, eps, use_norm = settings.pop()
    forward = {"bf16": bf16, "activation": activation, "eps": eps, "use_norm": use_norm}
    games = int(args.games_override or ref["games_per_pairing"])
    starts = X.shared_starts(env, games, int(ref["starts_seed"]))
    with torch.no_grad():
        xp = X.score_matrix(env, guards, strikes, starts, forward, args.chunk, frozenset(excluded))
    name = f"matrix_{games}.json" if not args.games_override else f"matrix_{games}_not_of_record.json"
    path = out / name
    path.write_text(json.dumps(X.crossplay_to_dict(xp) | {"starts_seed": int(ref["starts_seed"]), "device": str(args.device),
                                                          "gates_sha256": _sha256(out / "gates.toml"),
                                                          "of_record": not args.games_override}, indent=2) + "\n")
    runs = list(ref["reference_runs"])
    confidence = float(match["confidence"])
    loo = X.loo_check(xp, runs, confidence)
    result = {"matrix": name, "matrix_sha256": _sha256(path), "loo_pass": loo["pass"],
              "statistic_c": "gate" if loo["pass"] else "INFO",
              "loo_misses": [list(e) for e, ok in loo["per_entry"].items() if not ok],
              "reference_seed_values_info": {name_: [X.reference_value(xp, k, team, runs) for k in runs]
                                             for name_, team in X.STATISTIC_TEAM.items()}}
    (out / ("loo.json" if not args.games_override else "loo_not_of_record.json")).write_text(json.dumps(result, indent=2) + "\n")
    print(f"[R0] {name} sha256 {result['matrix_sha256']}; leave-one-out {'PASS' if loo['pass'] else 'FAIL (5.1-c becomes INFO)'}",
          flush=True)
    return result


def main(argv: list[str] | None = None) -> int:
    from svg_training.nus.method_cfg import LOCAL_METHOD
    from svg_training.nus.players import DEPLOY_REF
    from svg_training.nus.rules import LOCAL_RULES
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    for flag in ("--write-gates", "--check", "--score", "--run"):
        mode.add_argument(flag, action="store_true")
    parser.add_argument("--outputs-dir", type=Path, help="NUS's outputs/hangar folder (read only)")
    parser.add_argument("--out-dir", type=Path, default=REFERENCE_DIR)
    parser.add_argument("--actions-dir", type=Path, help="default: <out-dir>/actions")
    parser.add_argument("--rules", type=Path, default=LOCAL_RULES)
    parser.add_argument("--deploy", type=Path, default=DEPLOY_REF)
    parser.add_argument("--method", type=Path, default=LOCAL_METHOD)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--chunk", type=int, default=2 ** 2 * 2 ** 2, help="pairings per batch")
    parser.add_argument("--games-override", type=int, help="tests and smoke runs only: not of record")
    args = parser.parse_args(argv)
    out = _under_runs(args.out_dir)
    if args.write_gates:
        print(f"wrote {write_gates(out)}")
        return 0
    if args.outputs_dir is None:
        parser.error("--outputs-dir is required")
    args.actions_dir = args.actions_dir or out / "actions"
    gates = read_gates(out)
    if args.check or args.run:
        if check(args, out, gates)["stop"]:
            print("[R0] more failed conversions than the gate allows: stop", flush=True)
            return EXIT_STOP
    if args.score or args.run:
        score(args, out, gates)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
