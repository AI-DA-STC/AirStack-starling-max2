"""Score one arm against the R0 reference by the frozen 5.1 rule (plan section 4.3, task M8): the positive control C0 (NUS's own code,
new seeds), the negative control N0 (untrained actors), stage 5.1 (our seeds) and the variants 5.1b / 5.1c. Conda ``env_isaaclab``:

    cd <svg_training>; unset PYTHONPATH; PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/nus_phase5_score.py \
        --arm {c0|n0|s51|s51b|s51c} --write-gates            # first: verbatim copies of the arm's frozen tables
    ... --arm c0 --check --outputs-dir <NUS outputs/hangar> --runs <run> <run> <run>   # C0 only: conversion and gate (a) per entry
    ... --arm <arm> --score [--outputs-dir ... --runs ...] [--followup] [--device cuda]

* The reference is R0's folder (``runs/nus_port/phase5/reference``): its gates copy, ``conversions.json`` (entries that failed gate (a)
  leave every panel), ``weights/``, ``matrix_1000.json`` (reference x reference cells and APF columns, reused unchanged) and
  ``loo.json`` (whether 5.1-c is a gate or INFO). The arm's cells are scored on the same engine, starts, game count and action mode:
  each arm Guard against every reference Strike and the Strike entries of its own lineage, each reference Guard against each arm
  Strike, and both APF columns.
* Arms and their lineages: C0 - NUS's archive entries of the given runs (converted; gate (a) per entry as in R0; completion from the
  archive and the jobs' logs); N0 - one untrained actor per generation slot from our initialisation (seeds of the frozen table; 5.1-a
  not applicable; 5.1-b pools from the selection rule over the earlier N0 entries); 5.1 / 5.1b / 5.1c - our archives under
  ``runs/nus_port/phase5/<stage>/seed<seed>/`` (completion from the state file and ``status.json``).
* 5.1-b pools are rebuilt with ``crossplay.selection_pools`` (the selection rule with each lineage's run seed). ``--followup`` adds
  the table's follow-up seeds and uses the Welch interval (the spread rule then gives FAIL).
* Writes ``<out>/matrix_<games>.json``, ``<out>/result.json`` (every statistic a to d, the verdict, for N0 whether the rule failed it
  as required, and the 5.1-e INFO statistics with ``configs/nus_phase5_method.toml``'s margin and band) and ``<out>/gpu_hours.log``.

``--games-override`` (tests, smoke runs) marks every output "not of record". Everything is written under runs/. No numeric literal
other than 0, 1, -1, 2 (G2).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

RUNS_ROOT = ROOT / "runs"   # tests patch it
PHASE5 = RUNS_ROOT / "nus_port" / "phase5"
SOURCE_GATES = ROOT / "configs" / "nus_port.toml"
CONFIG = ROOT / "configs" / "nus_phase5_method.toml"
ARM_TABLE = {"c0": "phase5_positive_control", "n0": "phase5_negative_control", "s51": "phase5_method_match",
             "s51b": "phase5_method_variants", "s51c": "phase5_method_variants"}
TABLES = ("phase5_method_match", "phase3_converted_policy")
NON_FINITE = re.compile(r"Non-finite training metrics")


def _under_runs(path: Path) -> Path:
    resolved = Path(path).resolve()
    if RUNS_ROOT.resolve() not in (resolved, *resolved.parents):
        raise SystemExit(f"refusing: {resolved} is outside runs/")
    return resolved


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_gates(out: Path, arm: str) -> Path:
    import nus_phase5_reference as ref
    out = _under_runs(out)
    path = out / "gates.toml"
    if path.exists():
        raise SystemExit(f"refusing: {path} exists (a gates file is never edited after it is written)")
    text = SOURCE_GATES.read_text()
    tables = tuple(dict.fromkeys((ARM_TABLE[arm], *TABLES)))
    body = "\n".join(ref.table_text(text, t) for t in tables)
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {arm} gates: verbatim copies of {SOURCE_GATES.name} (sha256 {_sha256(SOURCE_GATES)}), written before any {arm} "
                    f"result.\n\n{body}")
    return path


def _jsonable(value):
    """Entry keys (named tuples) become "lineage/generation/team" strings."""
    if isinstance(value, dict):
        return {("/".join(map(str, k)) if isinstance(k, tuple) else k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


# ------------------------------------------------------------------------------------------------ arms
def arm_seeds(arm: str, gates: dict, followup: bool) -> list[int]:
    table = gates[ARM_TABLE[arm]]
    seeds = [int(s) for s in table["seeds"]]
    if followup:
        if "followup_seeds" not in table:
            raise SystemExit(f"[gates.{ARM_TABLE[arm]}] has no follow-up seeds")
        seeds += [int(s) for s in table["followup_seeds"]]
    return seeds


def our_lineages(stage: str, seeds: list[int], env, method, device) -> tuple[dict, dict, dict]:
    """Trees of our archived entries, completion (archived, non-finite aborts) and the lineages' run seeds."""
    import torch

    from svg_training.nus import crossplay as X
    from svg_training.nus.mappo import MappoActor
    trees, completion, run_seed = {}, {}, {}
    for seed in seeds:
        folder = PHASE5 / stage / f"seed{seed}"
        state = json.loads((folder / "self_play_state.json").read_text()) if (folder / "self_play_state.json").exists() else {"archive": []}
        status = json.loads((folder / "status.json").read_text()) if (folder / "status.json").exists() else {}
        lineage = f"o{seed}"
        for entry in state["archive"]:
            actor = MappoActor(env.obs_dim, method, env.deploy.layernorm_epsilon)
            actor.load_state_dict(torch.load(Path(entry["path"]) / "actor.pt", map_location="cpu", weights_only=True))
            trees[X.Entry(lineage, int(entry["generation"]), entry["team"])] = X._detach_tree(actor.to(device).trunk.tree())
        completion[lineage] = (len(state["archive"]), int(bool(status.get("nonfinite_abort"))))
        run_seed[lineage] = seed
    return trees, completion, run_seed


def nus_completion(outputs: Path, run: str, logs: list[Path], generations: int) -> tuple[int, int]:
    archived = sum(1 for g in range(1, generations + 1) if list((outputs / run / "archive").glob(f"{g:04d}_*")))
    aborts = sum(len(NON_FINITE.findall(p.read_text(errors="ignore"))) for p in logs if p.exists())
    return archived, aborts


# ------------------------------------------------------------------------------------------------ scoring
def score(args, out: Path, gates: dict) -> dict:
    import numpy as np
    import torch

    import nus_phase5_reference as ref
    from svg_training.nus import crossplay as X
    from svg_training.nus.actor import NusActor
    from svg_training.nus.mappo import tree_from_converted
    from svg_training.nus.method_cfg import load_method
    from svg_training.nus.replica_train import NusTrainEnv

    match = gates["phase5_method_match"]
    rules, deploy = ref._load_inputs(args)
    method = load_method(args.method)
    env = NusTrainEnv(rules, deploy, method, device=args.device)
    reference_dir = args.reference_dir
    r0 = tomllib.loads((reference_dir / "gates.toml").read_text())["gates"]["phase5_reference_rebuild"]
    ref_runs = list(r0["reference_runs"])
    games = int(args.games_override or match["games_per_pairing"])
    matrix_name = f"matrix_{games}.json" if not args.games_override else f"matrix_{games}_not_of_record.json"
    loo_name = "loo.json" if not args.games_override else "loo_not_of_record.json"
    base = X.crossplay_from_dict(json.loads((reference_dir / matrix_name).read_text()))
    loo = json.loads((reference_dir / loo_name).read_text())

    def converted(conversions: dict, weights: Path) -> tuple[dict, set]:
        trees, failed = {}, set()
        for row in conversions["entries"]:
            entry = X.Entry(row["lineage"], int(row["generation"]), row["team"])
            if not row["pass"]:
                failed.add(entry)
                continue
            actor = NusActor.load(weights / row["name"], team=row["team"], rules=rules, deploy=deploy, device=args.device)
            trees[entry] = tree_from_converted(actor._params)
            settings.add((actor.bf16, actor.activation_name, actor.eps, actor.use_norm))
        return trees, failed

    settings: set = set()
    ref_trees, ref_failed = converted(json.loads((reference_dir / "conversions.json").read_text()), reference_dir / "weights")
    seeds = arm_seeds(args.arm, gates, args.followup)
    if args.arm == "c0":
        conversions = json.loads((out / "conversions.json").read_text())
        if conversions["stop"]:
            raise SystemExit("C0: more failed conversions than allowed")
        arm_trees, arm_failed = converted(conversions, out / "weights")
        lineages = list(dict.fromkeys(row["lineage"] for row in conversions["entries"]))
        if len(lineages) != len(seeds):
            raise SystemExit("C0: the runs given do not match the table's seeds")
        run_seed = dict(zip(lineages, seeds))
        completion = {k: nus_completion(args.outputs_dir, k, list(args.nus_logs), int(match["generations"])) for k in lineages}
    elif args.arm == "n0":
        arm_trees, arm_failed, completion, run_seed = {}, set(), None, {}
        for seed in seeds:
            arm_trees |= X.untrained_trees(env, method, seed, int(match["generations"]))
            run_seed[f"n{seed}"] = seed
        settings.add((method.compute_dtype == "bfloat16", method.activation, deploy.layernorm_epsilon, method.use_layernorm))
    else:
        arm_trees, completion, run_seed = our_lineages(args.arm, seeds, env, method, args.device)
        arm_failed = set()
        settings.add((method.compute_dtype == "bfloat16", method.activation, deploy.layernorm_epsilon, method.use_layernorm))
    if len(settings) != 1:
        raise SystemExit("the arm and the reference do not share one network setting")
    bf16, activation, eps, use_norm = settings.pop()
    forward = {"bf16": bf16, "activation": activation, "eps": eps, "use_norm": use_norm}

    trees = ref_trees | arm_trees
    guards = list(base.guards) + [e for e in arm_trees if e.team == "guard"]
    strikes = list(base.strikes) + [e for e in arm_trees if e.team == "strike"]
    arm = set(arm_trees)
    pairs, cells = [], []
    for i, g in enumerate(guards):
        for j, s in enumerate(strikes):
            ref_cell = g not in arm and s not in arm
            own = g in arm and s in arm and g.lineage == s.lineage
            mixed = (g in arm) != (s in arm)
            if not ref_cell and (own or mixed) and g in trees and s in trees:
                pairs.append((trees[g], trees[s]))
                cells.append((i, j))
    apf = [(k, e) for k, e in enumerate(guards) if e in arm] + [(k, e) for k, e in enumerate(strikes) if e in arm]
    pairs += [(trees[e], None) if e.team == "guard" else (None, trees[e]) for _, e in apf]
    starts = X.shared_starts(env, games, int(r0["starts_seed"]))
    began = time.time()
    try:
        with torch.no_grad():
            counts = X.score_pairings(env, pairs, starts, forward, args.chunk)
    finally:
        from svg_training.nus.pauses import append_row
        append_row(out / "gpu_hours.log", {"group": args.arm, "stage": args.arm, "what": "score", "device": str(args.device),
                                           "note": "not of record" if args.games_override else None, "start": began, "end": time.time()})
    reached = np.full((len(guards), len(strikes)), np.nan)
    reached[: len(base.guards), : len(base.strikes)] = base.reached
    for (i, j), c in zip(cells, counts[: len(cells)]):
        reached[i, j] = c
    apf_s = np.concatenate((base.apf_strike_reached, np.full(len(guards) - len(base.guards), np.nan)))
    apf_g = np.concatenate((base.apf_guard_reached, np.full(len(strikes) - len(base.strikes), np.nan)))
    for (k, e), c in zip(apf, counts[len(cells):]):
        (apf_s if e.team == "guard" else apf_g)[k] = c
    xp = X.CrossPlay(tuple(guards), tuple(strikes), reached, games, apf_s, apf_g, frozenset(ref_failed | arm_failed | base.excluded))
    (out / matrix_name).write_text(json.dumps(X.crossplay_to_dict(xp) | {"arm": args.arm, "of_record": not args.games_override,
                                                                         "reference_matrix_sha256": _sha256(reference_dir / matrix_name)},
                                              indent=2) + "\n")
    pools = {}
    for lineage, seed in run_seed.items():
        entries = [e for e in arm_trees if e.lineage == lineage] + [e for e in arm_failed if e.lineage == lineage]
        pools |= X.selection_pools(entries, seed, method.max_learned_opponents, method.recent_opponents)
    gate = X.load_gate(args.gates_path or out / "gates.toml")
    ours = list(run_seed)
    result = X.method_match(xp, ours, ref_runs, gate, completion=completion, pools=pools, c_gated=loo["statistic_c"] == "gate",
                            followup=args.followup)
    info = tomllib.loads(CONFIG.read_text())["info_5_1_e"]
    lo, hi = info["generalist_band"]
    last_g = max(g for g in range(1, gate.generations + 1) if g % 2)
    last_s = max(g for g in range(1, gate.generations + 1) if not g % 2)
    result["info_5_1_e"] = {
        "last_mover_share": {k: X.last_mover_share(xp, k) for k in ours + ref_runs},
        "near_shutout_share": {k: X.near_shutout_share(xp, k, float(info["near_shutout_margin"])) for k in ours + ref_runs},
        "generalist_mean_ours": X.generalist_mean(xp, ours, last_g, last_s), "generalist_band": [lo, hi]}
    result |= {"arm": args.arm, "followup": args.followup, "games": games, "of_record": not args.games_override, "matrix": matrix_name,
               "matrix_sha256": _sha256(out / matrix_name), "gates_sha256": _sha256(out / "gates.toml"),
               "statistic_c_kind": loo["statistic_c"], "lineages_ours": ours, "lineages_reference": ref_runs}
    if args.arm == "n0":
        result["negative_control_failed_as_required"] = X.negative_control_ok(result)
    name = "result.json" if not args.games_override else "result_not_of_record.json"
    (out / name).write_text(json.dumps(_jsonable(result), indent=2, default=str) + "\n")
    v = result["verdict"]
    print(f"[{args.arm}] verdict {v['verdict']}; reasons {v['reasons']}", flush=True)
    for stat, r in result["statistics"]["d"].items():
        print(f"[{args.arm}] {stat}: diff {r['diff']:+.4f} interval [{r['low']:+.4f}, {r['high']:+.4f}] spread ratio "
              f"{r['spread_ratio']:.3f}", flush=True)
    return result


def main(argv: list[str] | None = None) -> int:
    import nus_phase5_reference as ref
    from svg_training.nus.method_cfg import LOCAL_METHOD
    from svg_training.nus.players import DEPLOY_REF
    from svg_training.nus.rules import LOCAL_RULES
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arm", required=True, choices=tuple(ARM_TABLE))
    mode = parser.add_mutually_exclusive_group(required=True)
    for flag in ("--write-gates", "--check", "--score"):
        mode.add_argument(flag, action="store_true")
    parser.add_argument("--out-dir", type=Path, help="default runs/nus_port/phase5/<arm>/score")
    parser.add_argument("--reference-dir", type=Path, default=PHASE5 / "reference")
    parser.add_argument("--outputs-dir", type=Path, help="C0: NUS's outputs/hangar folder (read only)")
    parser.add_argument("--runs", nargs="*", default=[], help="C0: the run folder names, in the table's seed order")
    parser.add_argument("--nus-logs", type=Path, nargs="*", default=[], help="C0: the jobs' logs (non-finite aborts)")
    parser.add_argument("--actions-dir", type=Path, help="C0: default <out-dir>/actions")
    parser.add_argument("--followup", action="store_true")
    parser.add_argument("--rules", type=Path, default=LOCAL_RULES)
    parser.add_argument("--deploy", type=Path, default=DEPLOY_REF)
    parser.add_argument("--method", type=Path, default=LOCAL_METHOD)
    parser.add_argument("--gates-path", type=Path, help="tests only")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--chunk", type=int, default=2 ** 2 * 2 ** 2)
    parser.add_argument("--games-override", type=int, help="tests and smoke runs only: not of record")
    args = parser.parse_args(argv)
    out = _under_runs(args.out_dir or PHASE5 / args.arm / "score")
    args.reference_dir = _under_runs(args.reference_dir)
    if args.write_gates:
        print(f"wrote {write_gates(out, args.arm)}")
        return 0
    gates = tomllib.loads((out / "gates.toml").read_text())["gates"]
    if args.check:
        if args.arm != "c0" or not args.outputs_dir or not args.runs:
            parser.error("--check is for --arm c0 with --outputs-dir and --runs")
        args.actions_dir = args.actions_dir or out / "actions"
        r0 = tomllib.loads((args.reference_dir / "gates.toml").read_text())["gates"]["phase5_reference_rebuild"]
        summary = ref.check_runs(args, out, gates["phase3_converted_policy"], list(args.runs), tuple(r0["generations"]),
                                 int(r0["max_failed_conversions"]))
        return ref.EXIT_STOP if summary["stop"] else 0
    score(args, out, gates)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
