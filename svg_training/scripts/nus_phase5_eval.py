"""The stage 5.2 evaluation (NUS port Phase 5, Task S5; plan section 5, ``[gates.phase5_tier1_training]``). Conda ``env_isaaclab``; CUDA
for runs of record, CPU for tests and the smoke:

    cd <svg_training>; unset PYTHONPATH; PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/nus_phase5_eval.py \
        --stage 5.2 --device cuda [--runs runs/nus_port/phase5/s52/seed1001 ...] [--info] [--crossplay]
    ... --stage 5.2 --not-of-record --reference-dir <folder with scores.json and per_game.npz> --games 16 --runs <smoke run>   # smoke

In order (every number from ``nus/tier1_metrics.py``; the pair metrics are Phase 4's, ``nus/ladder.py``):

1. **Refusals first.** A run of record needs the gate table FROZEN (it is PROPOSED until the gatekeeper freezes it), every reference
   file's sha256 equal to the one pinned in the table, the table's seeds and generations, every run folder complete and of record, and
   the method file the runs were trained with (sha256 in each ``run.json``). ``--not-of-record`` lifts the status and sha256 refusals for
   a smoke and stamps every output NOT OF RECORD; ``--stage 5.3`` is refused (Task S8, not built).
2. **gates.toml first**: a verbatim copy of the table, the sha256 of ``configs/nus_port.toml`` and of every reference file read; an
   existing different copy is refused (a gates file is never edited).
3. **Bars** from Phase 4 row 5's ``scores.json`` (``tier1_metrics.reference_bars``).
4. **Control C-1** first: ParkedGuard v S20 re-scored on the same starts must equal ``per_game.npz`` key ``ParkedGuard__S20__outcome``
   game by game; otherwise the run stops (exit 3) before any gated pairing, and ``result.json`` says STOPPED. The evaluation always runs
   the row's own safety filter path (the CUDA-graph path reproduces the fixed loop, not the row's early stop, and could fail C-1 for a
   reason that is not the checkpoint).
5. **Gated pairings** (G-1 to G-4, S-1) for each seed's last archived Guard and last archived Strike, ``games_per_pairing`` paired starts,
   inside the evaluation cap (``evaluation_gpu_hours``, group ``s52_eval``, pause-aware, CUDA only): a pairing that would pass the cap is
   not started and the run is ABORTED. Per pairing: the reach and hold rates with Wilson 95 % intervals, Phase 4's metrics, the INFO clamp
   share (pre-clamp position outside the keep-in box by more than the tolerance), non-finite actions and states.
6. **Verdicts**: per seed (every gate G-1 to G-4, S-1, F-2; F-1 by construction), then the stage (at least ``min_seeds_passing`` seeds).
7. **INFO** (``--info``, after the gated pairings, inside the same cap; dropped with a note when it would pass it): our Guards v P3S, our
   Strikes v the table's INFO Guards. **Cross-play** (``--crossplay``, last, its own cap ``info_crossplay_gpu_hours``, group
   ``s52_crossplay``): every archived Guard v every archived Strike of the same lineage; whatever does not fit is dropped and listed.
8. **Videos**: for each gated pairing two games (the first Strike win and the first hold among the first 16 slots), from the games
   themselves, saved as data in ``<out>/videos/pending/`` (``scripts/nus_render_pending.py --playback-label "tier 1"`` renders them).
9. ``scores.json``, ``per_game.npz``, ``result.json`` and ``record_draft.md`` in ``<out>`` (default ``runs/nus_port/phase5/s52/eval``).

Everything is written under runs/. No numeric literal other than 0, 1, -1, 2 (G2).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

RUNS_ROOT = ROOT / "runs"   # tests patch it
STAGE_DIR = RUNS_ROOT / "nus_port" / "phase5" / "s52"
GATES = ROOT / "configs" / "nus_port.toml"
TABLE = "phase5_tier1_training"
EXIT_REFUSED, EXIT_STOPPED = 2, 2 + 1


def _hour_s() -> float:
    import datetime
    return datetime.timedelta(hours=1).total_seconds()


def _under_runs(path: Path) -> Path:
    resolved = Path(path).resolve()
    if RUNS_ROOT.resolve() not in (resolved, *resolved.parents):
        raise SystemExit(f"refusing: {resolved} is outside runs/")
    return resolved


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _git_head() -> str:
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def table_text(source: str, table: str) -> str:
    """The verbatim text of ``[gates.<table>]`` up to the next table header."""
    found = re.search(rf"^\[gates\.{re.escape(table)}\]\n.*?(?=^\[|\Z)", source, flags=re.S | re.M)
    if found is None:
        raise SystemExit(f"[gates.{table}] not found in {GATES.name}")
    return found.group(0).rstrip() + "\n"


def write_gates(out: Path, references: dict[str, str], not_of_record: bool) -> Path:
    """``<out>/gates.toml``: the verbatim table, the sha256 of the gate file and of every reference file read. Refuses a different
    existing copy (never edited)."""
    text = table_text(GATES.read_text(), TABLE)
    head = [f"# stage 5.2 gates: a verbatim copy of {GATES.name} [gates.{TABLE}] (sha256 {_sha(GATES)}), written before any result."]
    head += [f"# reference {name}: sha256 {sha}" for name, sha in sorted(references.items())]
    if not_of_record:
        head.append("# NOT OF RECORD (smoke): the status and sha256 refusals were lifted")
    body = "\n".join(head) + "\n\n" + text
    path = out / "gates.toml"
    if path.exists() and path.read_text() != body:
        raise SystemExit(f"refusing: {path} exists and differs (a gates file is never edited after it is written)")
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


# ------------------------------------------------------------------------------------------------ runs and checkpoints
def checkpoints(run: Path, generations: int | None) -> dict[str, dict]:
    """The run's last archived Guard and last archived Strike (``self_play_state.json``); with ``generations`` (of record) the archive
    must hold exactly that many entries and the Guard must be generation ``generations - 1``, the Strike ``generations``."""
    state = json.loads((run / "self_play_state.json").read_text())
    archive = state["archive"]
    if generations is not None and len(archive) != generations:
        raise SystemExit(f"refusing: {run} archived {len(archive)} generations, the table asks for {generations}")
    out = {}
    for team in ("guard", "strike"):
        entries = [e for e in archive if e["team"] == team]
        if not entries:
            raise SystemExit(f"refusing: {run} has no archived {team} entry")
        out[team] = max(entries, key=lambda e: e["generation"])
    if generations is not None and (out["guard"]["generation"], out["strike"]["generation"]) != (generations - 1, generations):
        raise SystemExit(f"refusing: {run}'s last entries are not the Guard of generation {generations - 1} and the Strike of {generations}")
    return out


# ------------------------------------------------------------------------------------------------ one pairing
class Pairs:
    """Plays pairings on the evaluation's starts and keeps their rows, per-game outcomes and clips."""

    def __init__(self, ctx: dict, out: Path, video_kind: str):
        self.ctx, self.out, self.video_kind = ctx, out, video_kind
        self.rows: list[dict] = []
        self.per_game: dict = {}
        self.videos: list[str] = []
        self.last_seconds = 0.0

    def play(self, guard: str, strike: str, label: str, videos: bool) -> dict:
        from svg_training.nus import ladder as L
        from svg_training.nus import tier1_metrics as M
        c = self.ctx
        res, extras, _, seconds = L.play_game_pair(c["cfg"], c["geo"], c["row"], c["starts"], guard, strike, c["guards"], c["strikes"],
                                                   c["device"], c["seed"], c["video_slots"], None, c["rules"], clamp_tol_m=c["clamp_tol_m"])
        self.last_seconds = seconds
        row = L.pair_row(res, extras, c["settings"], c["geo"], c["filter_keepout_m"], c["contact_m"], guard, strike, None, True,
                         c["guards"] + c["strikes"])
        row["label"] = label
        row["hold"] = M.hold_of(row["reach"])
        row["unfinished_games"] = int((res.outcome == 0).sum())
        if row["unfinished_games"]:
            raise RuntimeError(f"{guard} v {strike}: games still running at the time limit (the scorer refuses)")
        row["clamp_share"] = M.clamp_share(extras["clamp_ticks"], extras["live_ticks"])
        row["nonfinite"] = int(res.nonfinite_actions.sum()) + int(extras["nonfinite_state"].sum())
        row["seconds"] = seconds
        self.rows.append(row)
        key = f"{guard}__{strike}"
        self.per_game.update({f"{key}__outcome": res.outcome.numpy(), f"{key}__end_step": res.end_step.numpy()})
        if videos and self.video_kind != "none":
            from nus_selfplay_train import save_recording
            for clip in L.video_clips(res, extras, c["geo"], c["video_slots"], False, c["geo"].height_m):
                rec = L.clip_recording(clip, c["geo"], c["guards"], c["strikes"], guard, strike, "hangar row 5, tier 1 (training simulator)",
                                       c["seed"])
                self.videos.append(str(save_recording(rec, self.out / "videos" / "pending" / f"{label}__{key}__{clip['kind']}.npz")))
        print(f"  {label} {key}: Strike reach {row['reach']['k']}/{row['reach']['n']} ({seconds:.0f} s)", flush=True)
        return {"row": row, "outcome": res.outcome}


class Cap:
    """A pause-aware GPU-hour cap of one group (CUDA only; on the CPU it never stops a run): a pairing is started only when the time so
    far plus the last pairing's time stays inside what the log leaves."""

    def __init__(self, hours: float, log: Path, group: str, pauses: Path, cuda: bool):
        from svg_training.nus.pauses import logged_gpu_hours
        self.cuda, self.log, self.group, self.pauses = cuda, log, group, pauses
        self.left_s = (float(hours) - logged_gpu_hours(log, group, pauses)) * _hour_s()
        self.began = time.time()

    def fits(self, next_seconds: float) -> bool:
        from svg_training.nus.pauses import effective_seconds
        return not self.cuda or effective_seconds(self.began, time.time(), self.pauses) + next_seconds <= self.left_s

    def close(self, device: str, seed_note: str) -> None:
        from svg_training.nus.pauses import append_row
        append_row(self.log, {"group": self.group, "stage": "s52", "what": "evaluation", "note": seed_note, "device": device,
                              "start": self.began, "end": time.time()})


# ------------------------------------------------------------------------------------------------ main
def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stage", required=True, choices=("5.2", "5.3"))
    p.add_argument("--runs", type=Path, nargs="+", help="run folders (default: runs/nus_port/phase5/s52/seed<seed> of the table's seeds)")
    p.add_argument("--out", type=Path, help="default runs/nus_port/phase5/s52/eval")
    p.add_argument("--device", default="cpu")
    p.add_argument("--method", type=Path, help="default configs/local/nus_method.toml (its sha256 must equal every run's)")
    p.add_argument("--info", action="store_true", help="the INFO pairings after the gated ones (same cap)")
    p.add_argument("--crossplay", action="store_true", help="the INFO within-lineage cross-play table, last (its own cap)")
    p.add_argument("--video-format", choices=("deferred", "none"), default="deferred")
    p.add_argument("--not-of-record", action="store_true", help="smoke: lift the status and sha256 refusals; every output NOT OF RECORD")
    p.add_argument("--reference-dir", type=Path, help="not of record only: a folder with scores.json and per_game.npz")
    p.add_argument("--games", type=int, help="not of record only: games per pairing (the first paired starts)")
    p.add_argument("--gpu-hours-log", type=Path, help="default runs/nus_port/phase5/s52/gpu_hours.log")
    p.add_argument("--pauses-log", type=Path)
    return p


def main(argv: list[str] | None = None) -> int:
    import numpy as np
    import torch

    from svg_training.core.starling_layer import resolve_params
    from svg_training.models.fitted import load_params
    from svg_training.nus import hangar as H
    from svg_training.nus import ladder as L
    from svg_training.nus import tier1_metrics as M
    from svg_training.nus.method_cfg import LOCAL_METHOD
    from svg_training.nus.pauses import PAUSES_LOG
    from svg_training.nus.players import register_trained
    from svg_training.nus.tier1_env import load_tier1, tier1_world

    args = make_parser().parse_args(argv)
    if args.stage == "5.3":
        print("refusing: stage 5.3 (the Isaac Lab cross-check) is Task S8 and is not built", file=sys.stderr)
        return EXIT_REFUSED
    smoke = bool(args.not_of_record)
    if (args.reference_dir or args.games) and not smoke:
        print("refusing: --reference-dir and --games are for --not-of-record runs only", file=sys.stderr)
        return EXIT_REFUSED
    table = tomllib.loads(GATES.read_text())["gates"][TABLE]
    if not str(table.get("status", "")).startswith("FROZEN") and not smoke:
        print(f"refusing: [gates.{TABLE}] is {table.get('status')!r}, not FROZEN (the gatekeeper freezes it before the first run)",
              file=sys.stderr)
        return EXIT_REFUSED
    M.check_confidence(table["confidence"])
    settings5 = load_tier1()
    ev = settings5["evaluation"]
    device = args.device
    if device.startswith("cuda") and not torch.cuda.is_available():
        print("refusing: --device cuda but no CUDA device", file=sys.stderr)
        return EXIT_REFUSED

    # ---- reference files and their sha256
    ref_dir = args.reference_dir
    files = {"starts": ROOT / table["starts_file"],
             "scores": (ref_dir / "scores.json") if ref_dir else ROOT / table["reference_scores"],
             "per_game": (ref_dir / "per_game.npz") if ref_dir else ROOT / table["reference_per_game"]}
    pinned = {"starts": table["starts_sha256"], "scores": table["reference_scores_sha256"], "per_game": table["reference_per_game_sha256"]}
    shas = {}
    for name, path in files.items():
        if not path.exists():
            print(f"refusing: reference file {path} is missing", file=sys.stderr)
            return EXIT_REFUSED
        shas[name] = _sha(path)
        if shas[name] != pinned[name] and not smoke:
            print(f"refusing: {path} sha256 differs from the one pinned in [gates.{TABLE}]", file=sys.stderr)
            return EXIT_REFUSED

    # ---- runs
    seeds = [int(s) for s in table["seeds"]]
    runs = [Path(r) for r in args.runs] if args.runs else [STAGE_DIR / f"seed{s}" for s in seeds]
    method_path = args.method or LOCAL_METHOD
    method_sha = _sha(method_path)
    plan = {}
    for run in runs:
        meta = json.loads((run / "run.json").read_text())
        status = json.loads((run / "status.json").read_text()) if (run / "status.json").exists() else {}
        if meta.get("method_sha256") != method_sha:
            print(f"refusing: {run} was trained with another method file (sha256 in run.json)", file=sys.stderr)
            return EXIT_REFUSED
        if meta.get("interface_version") != "0.2":
            print(f"refusing: {run} is not an interface v0.2 run", file=sys.stderr)
            return EXIT_REFUSED
        if not smoke and (meta.get("not_of_record") or status.get("status") != "complete" or int(meta["seed"]) not in seeds):
            print(f"refusing: {run} is not a complete run of record of a table seed", file=sys.stderr)
            return EXIT_REFUSED
        plan[f"seed{meta['seed']}"] = {"run": run, "meta": meta,
                                       "entries": checkpoints(run, None if smoke else int(table["generations"]))}
    if not smoke and sorted(int(v["meta"]["seed"]) for v in plan.values()) != sorted(seeds):
        print(f"refusing: a run of record scores every table seed {seeds}", file=sys.stderr)
        return EXIT_REFUSED

    out = _under_runs(args.out or STAGE_DIR / "eval")
    if (out / "result.json").exists():
        print(f"refusing: {out / 'result.json'} exists (an evaluation is never overwritten)", file=sys.stderr)
        return EXIT_REFUSED
    write_gates(out, shas, smoke)

    # ---- the game, the starts, the bars
    world = tier1_world(table["row"], filter_cuda_graph=False)
    settings = H.load_phase4()
    n = int(args.games or table["games_per_pairing"])
    starts = L.load_starts(files["starts"])
    if starts["starts_units"].shape[0] < n:
        print("refusing: the starts file holds fewer starts than the games per pairing", file=sys.stderr)
        return EXIT_REFUSED
    starts = {k: v[:n] for k, v in starts.items()}
    scores = json.loads(files["scores"].read_text())
    bars = M.reference_bars(scores, list(table["guard_strikes"]), list(table["strike_guards"]))
    keepout = 2 * float(load_params(resolve_params(world.cfg.starling.params))["filter"]["safety_radius_m"])
    ctx = {"cfg": world.cfg, "geo": world.geo, "row": world.row, "starts": starts, "guards": world.guards, "strikes": world.strikes,
           "device": device, "seed": int(settings["ladder"]["seed"]), "video_slots": min(int(settings5["videos"]["eval_video_slots"]), n),
           "rules": world.rules, "clamp_tol_m": world.clamp_tol_m, "settings": settings, "filter_keepout_m": keepout,
           "contact_m": world.cfg.contact.contact_m}
    pairs = Pairs(ctx, out, args.video_format)
    cuda = device.startswith("cuda")
    log = _under_runs(args.gpu_hours_log or STAGE_DIR / "gpu_hours.log")
    pauses = args.pauses_log or PAUSES_LOG
    cap = Cap(table["evaluation_gpu_hours"], log, ev["gpu_hours_groups"]["gated"], pauses, cuda)
    result: dict = {"stage": "5.2", "not_of_record": smoke, "bars": bars, "games_per_pairing": n, "filter_path": world.filter_path,
                    "evaluation_filter_note": "the row's own safety filter path (C-1 compares with it game by game)",
                    "reference_sha256": shas, "pinned_sha256_match": {k: shas[k] == pinned[k] for k in shas}, "seeds": {}, "info": [],
                    "crossplay": {"played": [], "dropped": []}, "commit": _git_head(), "machine": platform.node(), "device": device}

    def finish(code: int) -> int:
        cap.close(device, "smoke" if smoke else "")
        (out / "scores.json").write_text(json.dumps({"pairs": pairs.rows}, indent=2, sort_keys=True) + "\n")
        np.savez_compressed(out / "per_game.npz", **pairs.per_game)
        result["videos"] = pairs.videos
        (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        record_draft(out, result, pairs.rows)
        return code

    # ---- control C-1 first
    control = pairs.play(ev["control_guard"], ev["control_strike"], "control", videos=False)
    reference = np.load(files["per_game"])
    key = f"{ev['control_guard']}__{ev['control_strike']}__outcome"
    differ = M.control_differences(control["outcome"], torch.from_numpy(reference[key][:n]))
    result["control"] = {"pair": key, "games_differ": differ}
    if differ:
        result["verdict"] = M.stage_verdict({}, differ, int(table["min_seeds_passing"]))
        print(f"STOPPED: control C-1 differs from the reference in {differ} games (train-debug before any verdict)", file=sys.stderr)
        return finish(EXIT_STOPPED)

    # ---- gated pairings
    for seed, item in plan.items():
        names = {}
        for team, entry in item["entries"].items():
            name = f"{seed}_g{entry['generation']:02d}_{team}"
            register_trained(name, entry["path"], method_path)
            names[team] = name
        results = {}
        jobs = [(gate, names["guard"], bar["against"]) if bar["team"] == "guard" else (gate, bar["against"], names["strike"])
                for gate, bar in bars.items()]
        for gate, guard, strike in jobs:
            if not cap.fits(pairs.last_seconds):
                result["verdict"] = {"verdict": "ABORTED", "reason": "the evaluation cap would be passed before every gated pairing ran"}
                return finish(EXIT_STOPPED)
            played = pairs.play(guard, strike, seed, videos=True)
            results[gate] = {"reach": played["row"]["reach"], "nonfinite": played["row"]["nonfinite"]}
        result["seeds"][seed] = {**M.seed_verdict(results, bars, int(table["nonfinite_max"])), "checkpoints": names}
    result["verdict"] = M.stage_verdict(result["seeds"], 0, int(table["min_seeds_passing"]))
    if smoke:
        result["verdict"]["note"] = "NOT OF RECORD (smoke)"

    # ---- INFO pairings, same cap
    if args.info:
        for seed, item in plan.items():
            guard_name = f"{seed}_g{item['entries']['guard']['generation']:02d}_guard"
            strike_name = f"{seed}_g{item['entries']['strike']['generation']:02d}_strike"
            jobs = [(guard_name, s) for s in ev["info_guard_strikes"]] + [(g, strike_name) for g in ev["info_strike_guards"]]
            for guard, strike in jobs:
                if not cap.fits(pairs.last_seconds):
                    result["info"].append({"pair": f"{guard}__{strike}", "dropped": "the evaluation cap"})
                    continue
                pairs.play(guard, strike, f"info_{seed}", videos=False)
                result["info"].append({"pair": f"{guard}__{strike}", "played": True})

    # ---- INFO cross-play, its own cap
    if args.crossplay:
        cap.close(device, "gated and info")
        cap = Cap(table["info_crossplay_gpu_hours"], log, ev["gpu_hours_groups"]["crossplay"], pauses, cuda)
        for seed, item in plan.items():
            archive = json.loads((item["run"] / "self_play_state.json").read_text())["archive"]
            named = {}
            for e in archive:
                named[(e["team"], e["generation"])] = f"{seed}_g{e['generation']:02d}_{e['team']}"
                register_trained(named[(e["team"], e["generation"])], e["path"], method_path)
            for (gt, gg), guard in sorted(named.items()):
                for (st, sg), strike in sorted(named.items()):
                    if gt != "guard" or st != "strike":
                        continue
                    if not cap.fits(pairs.last_seconds):
                        result["crossplay"]["dropped"].append(f"{guard}__{strike}")
                        continue
                    pairs.play(guard, strike, f"crossplay_{seed}", videos=False)
                    result["crossplay"]["played"].append(f"{guard}__{strike}")
        if result["crossplay"]["dropped"]:
            result["crossplay"]["note"] = "pairings that would pass the cross-play cap were dropped (listed); the record says so"
    return finish(0)


# ------------------------------------------------------------------------------------------------ record
def record_draft(out: Path, result: dict, rows: list[dict]) -> Path:
    head = "NOT OF RECORD (smoke)" if result["not_of_record"] else result.get("verdict", {}).get("verdict", "incomplete")
    lines = [f"# NUS port Phase 5, stage 5.2 evaluation: training simulator, tier 1 (hangar game of Phase 4 row 5), record draft ({head})",
             "", "Observed in the training simulator, tier 1: the fitted Starling layer with the EXPLORATORY drone model (T5 = FAIL), the "
             "all-pairs safety filter, 3-D. Nothing here is a flight result.", "",
             f"- Commit `{result['commit']}`; machine `{result['machine']}`, device `{result['device']}`; {result['games_per_pairing']} "
             "games per pairing on the Phase 4 paired starts.",
             f"- Reference sha256 equal to the pinned ones: {json.dumps(result['pinned_sha256_match'])}.",
             f"- Safety filter: {result['evaluation_filter_note']}.",
             f"- Control C-1: {json.dumps(result.get('control'))}.",
             f"- Verdict: {json.dumps(result.get('verdict'))}.", "",
             "| Label | Guard | Strike | Strike reach k/n [95 %] | Hold [95 %] | Clamp share (INFO) | Non-finite |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        reach, hold, clamp = r["reach"], r["hold"], r["clamp_share"]
        lines.append(f"| {r['label']} | {r['guard']} | {r['strike']} | {reach['k']}/{reach['n']} [{reach['ci_low']:.3f}, {reach['ci_high']:.3f}] "
                     f"| [{hold['ci_low']:.3f}, {hold['ci_high']:.3f}] | {clamp['k']}/{clamp['n']} | {r['nonfinite']} |")
    lines += ["", "Bars (pass if our Wilson lower bound is above): " + ", ".join(f"{g} {b['bar']:.3f} v {b['against']}"
                                                                                for g, b in result["bars"].items()),
              "", "Claim strength: G-3 and G-4 (bar about 0.004) pass with as few as 8 holds in 1,000 games; G-1 and S-1 carry the claim.",
              "", "Videos:"] + [f"- `{p}`" for p in result.get("videos", [])]
    path = out / "record_draft.md"
    path.write_text("\n".join(lines) + "\n")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
