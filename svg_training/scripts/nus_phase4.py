"""One row of the Phase 4 transfer ladder (plan docs/plans/2026-11-18-nus-phase4-transfer-ladder.md, INFO runs: no gates).

    cd <svg_training>; unset PYTHONPATH; PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/nus_phase4.py \
        --row 4 [--device cuda] [--games N] [--accept-long]
    ... scripts/nus_phase4.py --row 6 --headless --device cuda        # Isaac Lab (after scripts/isaac_preflight.sh --approved-headless: exit 0)
    ... scripts/nus_phase4.py --make-starts                             # the paired starts file, once
    ... scripts/nus_phase4.py --w2-replay                               # row 1's exact check against W2 (CPU)
    ... scripts/nus_phase4.py --cuda-parity                             # the converted actors on cuda against the CPU (INFO)
    ... scripts/nus_phase4.py --render <row folder>                     # render the videos of a finished row (CPU)

Every pair of the row's blocks (``configs/nus_phase4.toml``) plays the paired starts (``runs/nus_port/phase4/starts.npz``), one batch of 1,000
games per pair, then the D5 metrics are written. Output folder ``runs/nus_port/phase4/<row>/`` (git-ignored; it holds partner values): ``gates.toml`` (written first,
``gates = []`` and the reading rules as text), ``scores.json``, ``scores.md``, ``per_game.npz``, ``clips.npz`` and ``videos/``. A row that already has a
``scores.json`` is refused. Exit 0 = the row ran and no reading rule stopped it; 3 = a reading rule stopped it (the result is still written); 4 = the
estimate is over the foreground limit (nothing was run: pass --accept-long); 2 = refused before launch.

Isaac rows keep ``score.py``'s order: only the standard library is imported at the top, refusals come before the launch, Isaac Sim starts
before torch is imported, one ``IsaacWorld`` of games x drones is reused for every pair, and the process leaves through ``os._exit``.
All results are observed in the training simulator (tier 1: replica, points, fitted drone; tier 2: Isaac Lab physics drone).
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

WORKERS = 2 * 2  # parallel renderers
EXIT_STOP, EXIT_LONG, EXIT_REFUSED = 2 + 1, 2 * 2, 2
HOUR_S = datetime.timedelta(hours=1).total_seconds()
STOPS_FILTER_OFF = "safety filter off (STANDARDS section 6.2 exception, Phase 4 ladder)"
READING_RULES = """# Reading rules (plan D5; PROPOSED, not gates)
1. ParkedGuard holds at least the settings' parked_stop_hold against ApfStrike on any row: the geometry closes the zone on its own. Stop; ask the owner.
2. A control row (2.1, 3a, 5a) that differs from its partner row in any game: stop, train-debug.
3. Row 1's replay of W2's starts differs in any game: stop.
4. Any upset, non-finite wrench or contact on rung 6: record it, then train-debug before the summary.
"""


def _row_of(settings: dict, row_id: str) -> dict:
    rows = {r["id"]: r for r in settings["row"]}
    if row_id not in rows:
        raise SystemExit(f"refusing: unknown row {row_id!r}; known: {list(rows)}")
    return rows[row_id]


def make_parser(isaac: bool = False) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--row")
    p.add_argument("--out", type=Path)
    p.add_argument("--games", type=int, help="override the settings' games per pair (tests only; a run of record uses the settings)")
    p.add_argument("--pairs", help="comma list of Guard:Strike pairs to run (tests only)")
    p.add_argument("--accept-long", action="store_true")
    p.add_argument("--estimate-only", action="store_true")
    p.add_argument("--make-starts", action="store_true")
    p.add_argument("--w2-replay", action="store_true")
    p.add_argument("--cuda-parity", action="store_true")
    p.add_argument("--render", type=Path)
    p.add_argument("--tables", help="comma list of row ids: print their committed-text tables (values equal to a local value read 'at the local value')")
    p.add_argument("--no-videos", action="store_true")
    if not isaac:
        p.add_argument("--device", default="cpu")
        p.add_argument("--headless", action="store_true")
    return p


def physics_problem(argv: list[str]) -> str | None:
    """With a physics row: the reason to refuse (exit 2) before Isaac Sim or torch is imported, else None."""
    import tomllib
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--row")
    pre.add_argument("--headless", action="store_true")
    pre.add_argument("--device", default="cpu")
    known, _ = pre.parse_known_args(argv)
    if known.row is None:
        return None
    settings = tomllib.loads((ROOT / "configs" / "nus_phase4.toml").read_text())
    row = next((r for r in settings["row"] if r["id"] == known.row), None)
    if row is None or row["drone"] != "physics":
        return None
    if not known.headless:
        return "a physics row starts Isaac Sim: add --headless (after scripts/isaac_preflight.sh --approved-headless exits 0)"
    if not known.device.startswith("cuda"):
        return "a physics row runs on the GPU: use --device cuda"
    return None


# ------------------------------------------------------------------------------------------------ helpers
def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _load_world_context(args):
    """Everything the row needs from the local files and the committed settings."""
    from svg_training.core.game_config import load_game_cfg
    from svg_training.nus import hangar as H
    from svg_training.nus import strategy as strategy_module
    from svg_training.nus.deploy import apply_overrides, load_deploy
    from svg_training.nus.rules import load_rules
    settings = H.load_phase4()
    base, _ = load_game_cfg(H.HANGAR_GAME, use_local=False)
    deploy = load_deploy(strategy_module.DEPLOY_PATH)
    rules = apply_overrides(load_rules(strategy_module.RULES_PATH), deploy)
    hangar = H.load_hangar(H.LOCAL_HANGAR)
    return settings, base, deploy, rules, hangar


def _pair_list(settings: dict, row: dict, restrict: str | None) -> list[tuple[str, str]]:
    from svg_training.nus.ladder import pairs_of_row
    pairs = pairs_of_row(settings, row)
    if restrict:
        wanted = {tuple(x.split(":")) for x in restrict.split(",")}
        pairs = [p for p in pairs if p in wanted]
    return pairs


def run_row(args, world_factory=None) -> int:
    import numpy as np
    import torch

    from svg_training.core.game_config import load_game_cfg  # noqa: F401
    from svg_training.nus import hangar as H
    from svg_training.nus import ladder as L
    from svg_training.nus import strategy as strategy_module
    from svg_training.nus.outputs import require_under_runs
    from svg_training.nus.players import ReplicaPlayer, parks_guard0, replica_for
    from svg_training.nus.rules import file_sha256

    settings, base, deploy, rules, hangar = _load_world_context(args)
    row = _row_of(settings, args.row)
    H.check_row(row)
    H.check_row_lint([r for r in settings["row"]])
    out = require_under_runs(args.out or L.PHASE4_DIR / f"row_{args.row}")
    if (out / "scores.json").exists():
        print(f"refusing: {out / 'scores.json'} exists (a row is never overwritten)", file=sys.stderr)
        return EXIT_REFUSED
    out.mkdir(parents=True, exist_ok=True)
    (out / "gates.toml").write_text(f'# Phase 4 row {row["id"]}: INFO run, no gates (plan D8). Written before the run.\ngates = []\n\n' + READING_RULES)
    device = args.device
    if device.startswith("cuda") and not torch.cuda.is_available():
        print("refusing: --device cuda but no CUDA device", file=sys.stderr)
        return EXIT_REFUSED
    geo = H.geometry(rules, deploy, hangar, base)
    starts = L.load_starts(L.STARTS_FILE)
    n = args.games or settings["ladder"]["games"]
    if starts["starts_units"].shape[0] < n:
        print("refusing: the starts file holds fewer starts than the games per pair", file=sys.stderr)
        return EXIT_REFUSED
    starts = {k: v[:n] for k, v in starts.items()}
    slots = settings["ladder"]["video_slots"]
    pairs = _pair_list(settings, row, args.pairs)
    guards, strikes = rules.guard_count, rules.strike_count
    replica = row["engine"] == "replica"
    cfg = None if replica else H.hangar_cfg(base, rules, deploy, hangar, row)
    from svg_training.core.starling_layer import resolve_params
    from svg_training.models.fitted import load_params
    filter_keepout = 2 * float(load_params(resolve_params(base.starling.params))["filter"]["safety_radius_m"])
    contact_m = base.contact.contact_m
    world = None
    if row["drone"] == "physics":
        from svg_training.core.physics_layer import load_game_physics_params
        params = load_game_physics_params(cfg)
        world = world_factory(n, guards + strikes, params, device)
    estimate_s = None
    if not replica:   # the estimate comes from the settings' warm-up ticks of the first pair, before anything is run (plan D7)
        estimate_s = L.warmup_estimate(cfg, geo, row, starts, pairs[0], guards, strikes, device, settings["ladder"]["seed"],
                                       settings["ladder"]["warmup_ticks"], world, rules) * len(pairs)
        print(f"estimate for the row from {settings['ladder']['warmup_ticks']} warm-up ticks: {estimate_s:.0f} s ({estimate_s / HOUR_S:.2f} h)", flush=True)
        if args.estimate_only or (estimate_s > settings["ladder"]["max_hours_foreground"] * HOUR_S and not args.accept_long):
            print("estimate over the foreground limit (or --estimate-only): nothing was run" if not args.estimate_only else "estimate only: nothing was run",
                  file=sys.stderr)
            (out / "gates.toml").unlink()
            out.rmdir() if not any(out.iterdir()) else None
            return EXIT_LONG
    previous = {}
    compare_to = row.get("equals")
    rows_declared = [r["id"] for r in settings["row"]]
    earlier = [r for r in rows_declared[: rows_declared.index(row["id"])] if (L.PHASE4_DIR / f"row_{r}" / "per_game.npz").exists()]
    before = earlier[-1] if earlier else None   # the nearest declared row before this one that was run (rows 2.1 and 2.2 may be skipped)
    for source in (before, compare_to):
        path = L.PHASE4_DIR / f"row_{source}" / "per_game.npz" if source else None
        if path is not None and path.exists():
            previous[source] = np.load(path)
    sim_cache = {}
    results, per_game, clips, seconds_total, game_steps = [], {}, {}, 0.0, 0
    started = time.perf_counter()
    for guard_name, strike_name in pairs:
        key = f"{guard_name}__{strike_name}"
        if replica:
            guard_player, strike_player = ReplicaPlayer(guard_name, device), ReplicaPlayer(strike_name, device)
            sim = sim_cache.setdefault("sim", replica_for("P3G", device))
            clock = time.perf_counter()
            res, extras = L.play_replica(sim, guard_player, strike_player, starts["starts_units"], geo.scale_m_per_unit, deploy.seconds_per_step,
                                         geo.hold_ticks, filter_keepout, (geo.keepout_guard_m, geo.keepout_strike_m), slots)
            if device.startswith("cuda"):
                torch.cuda.synchronize()
            seconds = time.perf_counter() - clock
            ticks_played = res.steps_played
        else:
            res, extras, game, seconds = L.play_game_pair(cfg, geo, row, starts, guard_name, strike_name, guards, strikes, device,
                                                          settings["ladder"]["seed"], slots, world, rules)
            ticks_played = res.steps_played
        seconds_total += seconds
        game_steps += n * ticks_played
        prev_outcome = None
        if before in previous and f"{key}__outcome" in previous[before].files:
            prev_outcome = torch.from_numpy(previous[before][f"{key}__outcome"])
        r = L.pair_row(res, extras, settings, geo, filter_keepout, contact_m, guard_name, strike_name, prev_outcome,
                       (not replica) and row["separation"] == "filter", guards + strikes)
        r["seconds"] = seconds
        if compare_to in previous and f"{key}__outcome" in previous[compare_to].files:
            other = previous[compare_to]
            hold = geo.hold_ticks   # a jump-motion game ends on the first tick of its partner step: compare partner steps
            mine_steps, other_steps = -(-res.end_step.numpy() // hold), -(-other[f"{key}__end_step"] // hold)
            r["control_games_differ"] = int(((other[f"{key}__outcome"] != res.outcome.numpy()) | (other_steps != mine_steps)).sum())
            r["control_outcomes_differ"] = int((other[f"{key}__outcome"] != res.outcome.numpy()).sum())
        results.append(r)
        ex = extras if isinstance(extras, dict) else {"any_min_3d_m": extras.any_min_3d_m, "team_min_3d_m": extras.team_min_3d_m}
        per_game.update({f"{key}__outcome": res.outcome.numpy(), f"{key}__end_step": res.end_step.numpy(),
                         f"{key}__closest_cross_m": res.closest_cross_m.numpy(), f"{key}__any_min_3d_m": ex["any_min_3d_m"].numpy()})
        for clip in L.video_clips(res, extras, geo, slots, replica, geo.height_m):
            tag = f"{key}__{clip['kind']}"
            clips[tag + "__pos_m"] = clip["pos_m"].numpy()
            clips[tag + "__meta"] = np.array(json.dumps({k: v for k, v in clip.items() if k != "pos_m"}))
        print(f"  {key}: Strike reach {r['reach']['k']}/{r['reach']['n']}", flush=True)
    total = time.perf_counter() - started
    reading1 = L.parked_hold_reading(results, settings["ladder"]["parked_stop_hold"])
    controls = [r["control_games_differ"] for r in results if "control_games_differ" in r]
    stop = bool(reading1["stop"]) or any(controls)
    meta = {"row": row, "commit": _git_head(), "machine": platform.node(), "python": platform.python_version(), "torch": torch.__version__,
            "gpu": torch.cuda.get_device_name(0) if device.startswith("cuda") else None, "device": device, "games": n, "pairs": len(pairs),
            "seed": settings["ladder"]["seed"], "seconds_total": total, "play_seconds": seconds_total, "estimate_seconds": estimate_s, "paired_against": before,
            "game_steps_per_s": game_steps / seconds_total if seconds_total else None,
            "drone_steps_per_s": game_steps * (guards + strikes) / seconds_total if seconds_total else None,
            "drones_per_game": guards + strikes, "tier": "replica (CPU/GPU tensors)" if replica else ("tier 2 (Isaac Lab physics drone)" if row["drone"] == "physics" else "tier 1"),
            "filter_off_note": STOPS_FILTER_OFF if row["separation"] in ("partner_push", "block") else None,
            "reading": {"parked_hold": reading1, "control_games_differ": controls},
            "sha256": {"rules": file_sha256(strategy_module.RULES_PATH), "deploy_w2": file_sha256(strategy_module.DEPLOY_PATH),
                       "hangar": file_sha256(H.LOCAL_HANGAR), "starts": file_sha256(L.STARTS_FILE), "settings": file_sha256(H.PHASE4_CONFIG),
                       "game_config": file_sha256(H.HANGAR_GAME)}}
    from svg_training.nus.players import DEPLOY_REF
    if DEPLOY_REF.exists():
        meta["sha256"]["deploy_ref"] = file_sha256(DEPLOY_REF)
    (out / "scores.json").write_text(json.dumps({"meta": meta, "pairs": results}, indent=2, sort_keys=True) + "\n")
    np.savez_compressed(out / "per_game.npz", **per_game)
    np.savez_compressed(out / "clips.npz", **clips)
    (out / "scores.md").write_text(_scores_md(meta, results))
    print(f"wrote {out / 'scores.json'} ({total:.0f} s, {meta['game_steps_per_s']} game-steps/s)", flush=True)
    if not args.no_videos:
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--render", str(out)], check=False)
    if stop:
        print(f"READING RULE STOP: parked {reading1}, control differences {controls}", file=sys.stderr)
        return EXIT_STOP
    return 0


def _scores_md(meta: dict, rows: list[dict]) -> str:
    lines = [f"# Phase 4 row {meta['row']['id']} (private: holds partner-derived values)", "",
             "| Guard | Strike | Strike reach k/n | 95 % interval | reach time median s | closest cross 3-D min m | rule breach | filter breach | contact | paired change |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        c = r["reach"]
        lines.append(f"| {r['guard']} | {r['strike']} | {c['k']}/{c['n']} | [{c['ci_low']:.3f}, {c['ci_high']:.3f}] | {r['reach_time_s']['median']} | "
                     f"{r['closest_cross_3d']['min']} | {r['rule_breach']['k']}/{r['rule_breach']['n']} | {r['filter_breach']['k']}/{r['filter_breach']['n']} | "
                     f"{r['contact']['k']}/{r['contact']['n']} | {r.get('paired_change')} |")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------------------ other modes
def make_starts(args) -> int:
    from svg_training.nus import ladder as L
    settings, base, deploy, rules, hangar = _load_world_context(args)
    path = L.make_starts(rules, settings["ladder"]["games"], settings["ladder"]["seed"], settings["ladder"]["jitter_m"])
    from svg_training.nus.rules import file_sha256
    print(f"wrote {path.name}, sha256 {file_sha256(path)}")
    return 0


def w2_replay(args) -> int:
    """Row 1's exact check (reading rule 3): on W2's 1,000 shared starts the replica path of ``P3G`` against ``ApfStrike`` and of
    ``ApfGuard`` against ``P3S`` equals a fresh ``play_arm`` game by game, and W2's counts. CPU."""
    import numpy as np
    import torch

    from svg_training.nus import ladder as L
    from svg_training.nus.apf import NusApf
    from svg_training.nus.deploy import REFERENCE_DIR
    from svg_training.nus.outcome import play_arm
    from svg_training.nus.players import ReplicaPlayer, replica_for
    settings, base, deploy, rules, hangar = _load_world_context(args)
    from svg_training.nus import hangar as H
    geo = H.geometry(rules, deploy, hangar, base)
    starts = torch.from_numpy(np.load(REFERENCE_DIR / "starts.npz")["pos"])
    w2 = json.loads((L.RUNS_DIR / "nus_port" / "phase3_outcome_parity.json").read_text())
    sim, apf = replica_for("P3G"), NusApf(rules, deploy)
    report = {"games": int(starts.shape[0]), "arms": {}}
    ok = True
    for team, guard_name, strike_name in (("guard", "P3G", "ApfStrike"), ("strike", "ApfGuard", "P3S")):
        player = ReplicaPlayer(guard_name if team == "guard" else strike_name)
        arm = play_arm(sim, apf, team, starts, player.actor.act_units)
        res, _ = L.play_replica(sim, ReplicaPlayer(guard_name), ReplicaPlayer(strike_name), starts, geo.scale_m_per_unit, deploy.seconds_per_step,
                                geo.hold_ticks, 0.0, (0.0, 0.0))
        ours = (res.outcome == 1)
        differ = int((ours != arm.reached).sum())
        w2_reached = int(w2["teams"][team]["converted_reached"])
        report["arms"][team] = {"games_differ_from_play_arm": differ, "reached": int(ours.sum()), "w2_converted_reached": w2_reached}
        ok &= differ == 0 and int(ours.sum()) == w2_reached
    report["equal"] = ok
    out = L.PHASE4_DIR / "w2_replay.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if ok else EXIT_STOP


def cuda_parity(args) -> int:
    """Gate (a)'s error with the actor on cuda (INFO, same limit): the W2 pair on W2's reference observations and the archive pair on W3's, all
    the observation rows of each file."""
    import numpy as np
    import torch

    from svg_training.nus import strategy as strategy_module
    from svg_training.nus.actor import NusActor
    from svg_training.nus.deploy import REFERENCE_DIR, apply_overrides, load_deploy, weights_folder
    from svg_training.nus.players import DEPLOY_REF
    from svg_training.nus.rules import load_rules
    import tomllib
    gate = tomllib.loads((ROOT / "configs" / "nus_port.toml").read_text())["gates"]["phase3_converted_policy"]
    limit = float(gate["max_action_error_units_per_step"])
    out = {}
    for label, deploy_file, ref_dir in (("w2", strategy_module.DEPLOY_PATH, REFERENCE_DIR), ("reference", DEPLOY_REF, REFERENCE_DIR.parent / "w3" / "reference")):
        if not Path(deploy_file).exists():
            continue
        deploy = load_deploy(deploy_file)
        rules = apply_overrides(load_rules(strategy_module.RULES_PATH), deploy)
        for team in ("guard", "strike"):
            data = np.load(ref_dir / f"actions_{team}.npz")
            obs, expected = torch.from_numpy(data["obs"]), torch.from_numpy(data["actions"])
            actor = NusActor.load(weights_folder(deploy, team), team=team, rules=rules, deploy=deploy, device=args.device)
            got = actor.act_units(obs.to(args.device)).cpu()
            out[f"{label}_{team}"] = {"max_error_units": float((got - expected).abs().max()), "rows": int(obs.shape[0] * obs.shape[1]), "limit": limit}
    ok = all(v["max_error_units"] <= v["limit"] for v in out.values())
    print(json.dumps({"device": args.device, "within_limit": ok, "teams": out}))
    return 0 if ok else EXIT_STOP


def tables(row_ids: str) -> int:
    """Markdown tables of finished rows for a committed record, passed through the protected-value check (``ladder.check_text``)."""
    from svg_training.nus import hangar as H
    from svg_training.nus import ladder as L
    from svg_training.nus import strategy as strategy_module
    from svg_training.nus.outputs import protected_numbers
    protected = protected_numbers(strategy_module.RULES_PATH, strategy_module.DEPLOY_PATH, hangar_path=H.LOCAL_HANGAR)
    for row_id in row_ids.split(","):
        import numpy as np
        settings = H.load_phase4()
        declared = [r["id"] for r in settings["row"]]
        row = next(r for r in settings["row"] if r["id"] == row_id)
        data = json.loads((L.PHASE4_DIR / f"row_{row_id}" / "scores.json").read_text())
        earlier = [r for r in declared[: declared.index(row_id)] if (L.PHASE4_DIR / f"row_{r}" / "per_game.npz").exists()]
        pairs = data["pairs"]
        if earlier:   # the paired change is against the nearest declared row that ran (recomputed from the per_game files)
            pairs = L.paired_against(pairs, np.load(L.PHASE4_DIR / f"row_{earlier[-1]}" / "per_game.npz"), np.load(L.PHASE4_DIR / f"row_{row_id}" / "per_game.npz"))
        coarse = row["engine"] == "replica" or row["motion"] == "jump"
        text = (f"### Row {row_id}\n\n" + L.rung_table_md(pairs, protected, coarse, earlier[-1] if earlier else None) + "\n"
                + L.extras_table_md(data["pairs"], protected))
        L.check_text(text, protected)
        print(text)
    return 0


def render_videos(folder: Path) -> int:
    """Render the clips of a finished row into <folder>/videos/ (CPU; format in the settings' [video]), four at a time."""
    import numpy as np
    from concurrent.futures import ProcessPoolExecutor

    from svg_training.nus import hangar as H
    from svg_training.nus import ladder as L
    settings, base, deploy, rules, hangar = _load_world_context(argparse.Namespace())
    geo = H.geometry(rules, deploy, hangar, base)
    data = np.load(folder / "clips.npz")
    scores = json.loads((folder / "scores.json").read_text())
    label = f"phase 4 row {scores['meta']['row']['id']}: " + "partner hangar ladder"
    jobs = []
    for name in data.files:
        if name.endswith("__pos_m"):
            tag = name[: -len("__pos_m")]
            guard, strike, kind = tag.split("__")
            jobs.append((str(folder), tag, guard, strike, kind, label, settings["ladder"]["seed"]))
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        for path in pool.map(_render_one, jobs):
            print(f"  video {path}", flush=True)
    return 0


def _render_one(job):
    import numpy as np
    import torch

    from svg_training.nus import hangar as H
    from svg_training.nus import ladder as L
    from svg_training.core.game_config import TICK_S
    from svg_training.viz.replay import render_replay
    folder, tag, guard, strike, kind, label, seed = job
    folder = Path(folder)
    settings, base, deploy, rules, hangar = _load_world_context(argparse.Namespace())
    geo = H.geometry(rules, deploy, hangar, base)
    data = np.load(folder / "clips.npz")
    meta = json.loads(str(data[tag + "__meta"]))
    clip = {**meta, "pos_m": torch.from_numpy(data[tag + "__pos_m"])}
    rec = L.clip_recording(clip, geo, rules.guard_count, rules.strike_count, guard, strike, label, seed)
    path = folder / "videos" / f"{guard}_vs_{strike}_{kind}.mp4"
    video = settings["video"]
    render_replay(rec, path, speed=video["speed"], fps=video["fps"], dpi=video["dpi"], playback_label=f"{video['speed'] * video['fps'] * TICK_S:g}x real time")
    return path


def main(argv=None, world_factory=None) -> int:
    args = make_parser().parse_args(argv) if not isinstance(argv, argparse.Namespace) else argv
    if args.render:
        return render_videos(args.render)
    if args.tables:
        return tables(args.tables)
    if args.make_starts:
        return make_starts(args)
    if args.w2_replay:
        return w2_replay(args)
    if args.cuda_parity:
        return cuda_parity(args)
    if not args.row:
        print("refusing: give --row <id> (or a mode)", file=sys.stderr)
        return EXIT_REFUSED
    return run_row(args, world_factory)


def _main_cli() -> int:
    argv = sys.argv[1:]
    problem = physics_problem(argv)
    if problem is not None:
        print(f"refusing: {problem}", file=sys.stderr)
        return EXIT_REFUSED
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--row")
    row_id = pre.parse_known_args(argv)[0].row
    physics = False
    if row_id:
        import tomllib
        settings = tomllib.loads((ROOT / "configs" / "nus_phase4.toml").read_text())
        physics = any(r["id"] == row_id and r["drone"] == "physics" for r in settings["row"])
    if not physics:
        return main()
    from _isaac_app import start_headless
    args, _app = start_headless(make_parser(isaac=True))
    args.device = getattr(args, "device", "cuda")
    code = 1
    try:
        from score import _isaac_world_factory
        code = main(args, _isaac_world_factory)
    except BaseException:  # noqa: BLE001
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)  # never simulation_app.close() (it swallows exit codes in the container)
    return code


if __name__ == "__main__":
    sys.exit(_main_cli())
