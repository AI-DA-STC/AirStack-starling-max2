#!/usr/bin/env python
"""STE L3-L6 pipeline check, L5 runs: 3-D Isaac Lab clips of a FINISHED L5 run, beside its 2-D top-down GIFs (owner,
25 Nov 2026: "make the L5 clips render in 3D isaac lab automatically along with the 2D top view"). A post-run script:
the driver (``scripts/ste_exploit_l012.py``) and the gate files are not touched, and nothing is written in the run
folder except ``--out`` (default ``<run>/videos3d``).

    # after nvidia-smi (>= 8 GB free); the script runs scripts/isaac_preflight.sh --approved-headless --allow-siblings
    # itself before Isaac starts; through the launcher (GPU-h logged), --run-dir = the clips' own folder:
    unset PYTHONPATH
    scripts/ste_job.py launch --task <the run's [run] task, L5.1-L5.4> --name l5_clips3d_<run> \\
        --run-dir <run>/videos3d --min-s 30 --gpu-h 0.1 --settings configs/ste_learning.toml -- \\
        <python> scripts/ste_l5_clips3d.py --run-dir <run> [--out <run>/videos3d]
    # CPU, writes nothing: the checks and the picks only
    <python> scripts/ste_l5_clips3d.py --run-dir <run> --plan-only

**Read** (all read only): the run's gate file copy ``gates.toml`` (its sha256 = the pin ``gates.sha256`` = its
``results.json``; the game files unchanged since), ``run.json`` (variant, side), ``results.json`` (complete),
``agent_final.pt`` through the route's loader (velocity: ``exploit_train.team_from_modules``; the two-level skills
route: ``skill_team_from_modules`` with the dispatch built as the driver's evaluation built it: the training game,
``[trainer] num_games``, the side's train seed), ``eval_info.npz`` (the INFO batch: the trained team against every
script of the other team, the run's own opponent included, on T44's starts; ``eval_final.npz`` holds the same pairing
for the run's opponent only) and ``checkpoint.latest`` (the opponent pool's game counters).

**The key games (rule fixed in this code before anything is rendered; :data:`RULE`).**
1. The worst cell: the opponent against which the trained team's win rate in the INFO batch is lowest (an unfinished
   game is not a win, as the driver counts), leaving out the opponents of ``[players] z_up_info`` when the gate file
   has that label (all of them if that leaves none); a tie goes to the first in ``[players]`` order. In that cell the
   lowest game index the trained team WON and the lowest it LOST (the other team's win; an unfinished game is
   neither), each if one exists.
2. The opponent met most in training: per game slot g of the pool, the opponents of its finished training games
   ``pool_draw(seed, g, k)`` for k < the slot's counter in ``checkpoint.latest`` (their total equals the train log's
   games ended), counted per opponent; a tie goes to the first in ``[players]`` order. With the pool off, the run's
   fixed opponent. Its game: the lowest game index of its INFO cell that finished, not already picked. If that
   opponent is the worst cell's, no third game (the cell is shown already).

**Replay check.** The whole INFO batch is played again on the run's device (``viz/replay3d.capture_trained``: T44's
starts, every cell, the trained team held ``decision_ticks``, mean actions / argmax choices; the batch-mates matter,
the safety filter's early stop is batch-wide). A picked game is drawn only if it equals the run's recorded game:
outcome, end step, tags, Strike drones left and start positions exactly, closest approach within the L0.11 gate file's
same-seed tolerance (0 on the CPU). A game that differs is recorded in ``clips3d.json`` and nothing is drawn from it
(exit 1). The batch's own agreement is reported.

**Drawn** with the VID-1 tooling (``scripts/make_ste_3d.py``'s ``render``, in an Isaac child process, headless;
``configs/ste_video.toml``): two cameras (top view, 3-D view), raw frames under ``<out>/work/``, then this script's own
encode (the VID-1 overlay, tag crosses, MP4 and GIF): ``<out>/<stem>_{top,3d}.{mp4,gif}``. ``<out>/clips3d.json``:
the rule, the cell table, the training counts, the picks, the checks and the files; ``complete: true`` is written
last. Visual tooling: no gate, no record, no ledger row besides the launcher's GPU-hours.

Exit codes: 0 done; 1 a picked game differs from the record (nothing drawn from it; the others are drawn); 2 refused
(a missing or inconsistent run file, a finished ``--out``, a device that is not the record's); 3 the render or the
encode failed; 11 the GPU is busy (the preflight's code). Observed in the training simulator; not a flight."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402

EXIT_DONE, EXIT_MISMATCH, EXIT_REFUSED, EXIT_RENDER, EXIT_GPU_BUSY = 0, 1, 2, 3, 11
CLIPS_JSON = "clips3d.json"
DEFAULT_OUT = "videos3d"
RUN_FILES = ("gates.toml", "gates.sha256", "run.json", "results.json", "agent_final.pt", "eval_info.npz",
             "eval_final.npz")
CHECKPOINT = "checkpoint.latest"          # ste/run_contract.CHECKPOINT_NAME
TRAIN_LOG = "train_log.jsonl"
UNFINISHED = 0
RULE = ("Fixed in scripts/ste_l5_clips3d.py before rendering. (1) Worst cell: the opponent with the trained team's "
        "lowest win rate in the run's INFO batch (eval_info.npz; an unfinished game is not a win), the [players] "
        "z_up_info opponents left out when the gate file has that label (all kept if that leaves none), a tie to the "
        "first in [players] order; in that cell the lowest game index the trained team won and the lowest it lost "
        "(the other team's win), each if one exists. (2) The opponent met most in training: finished training games "
        "per opponent from pool_draw(seed, slot, k) for k below each slot's counter in checkpoint.latest (the pool "
        "off: the run's fixed opponent), a tie to the first in [players] order; its game: the lowest game index of "
        "its INFO cell that finished and is not already picked; none if it is the worst cell's opponent. A game is "
        "drawn only if its replay equals the recorded game (outcome, end step, tags, Strike drones left, start "
        "positions; closest approach within the same-seed tolerance).")


def say(text: str) -> None:
    print(f"[l5 clips3d] {text}", flush=True)


class Refused(Exception):
    """Bad input: exit 2, nothing drawn."""


# ============================================================================================ reading the run
def load_run(run: Path) -> dict:
    """The finished run's files, checked (Refused names the first problem)."""
    from svg_training.ste import exploit

    for name in RUN_FILES:
        if not (run / name).is_file():
            raise Refused(f"{run} has no {name} (not a finished run folder)")
    res = json.loads((run / "results.json").read_text())
    if res.get("complete") is not True:
        raise Refused(f"{run}/results.json is not complete")
    try:
        gates = exploit.load_gates(run / "gates.toml")
    except (OSError, ValueError) as err:
        raise Refused(f"{run}/gates.toml: {err}") from err
    pinned = (run / "gates.sha256").read_text().strip()
    if not (gates.sha256 == pinned == res.get("gates_sha256")):
        raise Refused(f"{run}: the gate file copy {gates.sha256}, the pin {pinned} and results.json "
                      f"{res.get('gates_sha256')} are not one gate file")
    problems = exploit.game_file_problems(gates)
    if problems:
        raise Refused(f"{run}: game files changed since the run: " + "; ".join(problems))
    ref_path = exploit.ROOT / gates.reference["file"]
    if exploit.sha256_file(ref_path) != gates.reference["sha256"]:
        raise Refused(f"{ref_path}: sha256 is not the gate file's [reference] sha256")
    meta = json.loads((run / "run.json").read_text())
    if meta.get("run0"):
        raise Refused(f"{run} is a run 0 (its own fixed opponent, no INFO batch of record): not an L5 run")
    side, variant = meta.get("side"), meta.get("variant")
    if side not in exploit.SIDES or side != res.get("side") or variant != res.get("variant"):
        raise Refused(f"{run}: run.json (side {side!r}, variant {variant!r}) and results.json (side "
                      f"{res.get('side')!r}, variant {res.get('variant')!r}) disagree")
    if variant not in gates.variants:
        raise Refused(f"{run}: variant {variant!r} is not in its gate file")
    if gates.learner.skills and gates.learner.choice != exploit.skills.TWO_LEVEL:
        raise Refused(f"{run}: [learner] choice {gates.learner.choice!r}: only the velocity route and the two-level "
                      f"skills route are drawn")
    with np.load(run / "eval_info.npz") as d:
        info = {k: d[k] for k in d.files}
    return {"run": run, "gates": gates, "res": res, "meta": meta, "side": side, "variant": variant, "info": info}


def other_team(side: str) -> str:
    return "guard" if side == "strike" else "strike"


def won_code(side: str) -> int:
    from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
    return STRIKE_WIN if side == "strike" else GUARD_WIN


def lost_code(side: str) -> int:
    from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
    return GUARD_WIN if side == "strike" else STRIKE_WIN


def info_table(d: dict) -> list[dict]:
    """One row per INFO cell, in the driver's order (``info_cells``): the opponent, its cell index and the trained team's
    wins, losses and unfinished games of the record. Refused if the batch's size or its counts disagree with
    results.json's ``info`` block (the cell order must be the driver's)."""
    import ste_exploit_l012 as driver
    from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN

    gates, side = d["gates"], d["side"]
    cells = driver.info_cells(gates, side)
    n = int(gates.run["eval_games"])
    out = d["info"]["outcome"]
    if out.shape[0] != len(cells) * n:
        raise Refused(f"eval_info.npz holds {out.shape[0]} games, the gate file's INFO batch {len(cells)} x {n}")
    z_up = set(gates.players.get("z_up_info", []))
    rows = []
    for k, cell in enumerate(cells):
        o = out[k * n:(k + 1) * n]
        opp = cell[0] if side == "strike" else cell[1]
        label = f"{cell[0]} v {cell[1]}"
        rec = d["res"].get("info", {}).get(label)
        holds, reaches = int((o == GUARD_WIN).sum()), int((o == STRIKE_WIN).sum())
        unfinished = int((o == UNFINISHED).sum())   # results.json "games" counts the finished games only
        if rec is None or (int(rec["holds"]), int(rec["reaches"]), int(rec["games"]), int(rec["unfinished"])) != (
                holds, reaches, n - unfinished, unfinished):
            raise Refused(f"eval_info.npz cell {k} ({label}): holds {holds}, reaches {reaches} of {n}; results.json "
                          f"info says {rec}")
        wins, losses = int((o == won_code(side)).sum()), int((o == lost_code(side)).sum())
        rows.append({"cell_index": k, "cell": label, "opponent": opp, "games": n, "wins": wins, "losses": losses,
                     "unfinished": unfinished, "rate": wins / n, "z_up_info": opp in z_up})
    return rows


def worst_cell(rows: list[dict]) -> dict:
    """Rule step 1: the lowest win rate, z_up_info opponents left out (all kept if none is left), first on a tie."""
    pool = [r for r in rows if not r["z_up_info"]] or rows
    return min(pool, key=lambda r: (r["rate"], r["cell_index"]))


def training_meetings(d: dict, chunk: int = 64) -> dict:
    """Rule step 2: finished training games per opponent ({"source", "counts", "most", ...}). Batched over the slots,
    in chunks of game numbers (no per-game loop)."""
    import torch

    from svg_training.ste import exploit, pool

    gates, side, run = d["gates"], d["side"], d["run"]
    other = other_team(side)
    if not gates.pool["enabled"]:
        opp = exploit.opponent_of(gates, d["variant"], side)
        return {"source": "the pool is off: every training game against the run's fixed opponent", "counts": None,
                "most": opp}
    members = pool.pool_members(gates.players, other)
    if not (run / CHECKPOINT).is_file():
        raise Refused(f"{run} has no {CHECKPOINT}: the pool's game counters are needed for the training counts")
    ck = torch.load(run / CHECKPOINT, map_location="cpu", weights_only=False)
    state = ck.get("state", {}) if isinstance(ck, dict) else {}
    if state.get("phase") != "done":
        raise Refused(f"{run}/{CHECKPOINT}: phase {state.get('phase')!r}, not done")
    ps = state.get("learner", {}).get("opponent_pool")
    if ps is None or list(ps["names"]) != members or int(ps["seed"]) != int(gates.pool["seed"]):
        raise Refused(f"{run}/{CHECKPOINT}: its pool state is not the gate file's pool ({members}, seed "
                      f"{gates.pool['seed']})")
    k_slot = ps["k"].to(torch.long).cpu()
    counts = torch.zeros(len(members), dtype=torch.long)
    slots = torch.arange(k_slot.numel(), dtype=torch.long)
    top = int(k_slot.max()) if k_slot.numel() else 0
    for k0 in range(0, top, chunk):
        ks = torch.arange(k0, min(k0 + chunk, top), dtype=torch.long)
        kk = ks[None, :].expand(slots.numel(), -1).contiguous()
        ss = slots[:, None].expand(-1, ks.numel()).contiguous()
        draw = pool.pool_draw(int(ps["seed"]), ss, kk, len(members))
        counts += torch.bincount(draw[kk < k_slot[:, None]], minlength=len(members))
    counts_d = {m: int(c) for m, c in zip(members, counts.tolist())}
    order = gates.players[pool.TEAM_PLAYERS[other]]
    most = max(members, key=lambda m: (counts_d[m], -order.index(m)))
    out = {"source": f"pool_draw over each slot's counter in {CHECKPOINT} (finished training games)",
           "counts": counts_d, "most": most, "games_total": int(k_slot.sum())}
    log = run / TRAIN_LOG
    if log.is_file():
        ended = sum(int(json.loads(x).get("games_ended", 0)) for x in log.read_text().splitlines() if x.strip())
        out["train_log_games_ended"] = ended
        out["agrees_with_train_log"] = ended == out["games_total"]
    return out


def pick_games(d: dict, rows: list[dict], worst: dict, most: str) -> list[dict]:
    """The key games (rule in :data:`RULE`): [{"pick", "opponent", "cell_index", "game_index", "global_index"}]."""
    side, out = d["side"], d["info"]["outcome"]
    n = int(d["gates"].run["eval_games"])
    picks = []
    k = worst["cell_index"]
    cell = out[k * n:(k + 1) * n]
    for name, code in (("worst_won", won_code(side)), ("worst_lost", lost_code(side))):
        hit = np.flatnonzero(cell == code)
        if hit.size:
            picks.append({"pick": name, "opponent": worst["opponent"], "cell_index": k, "game_index": int(hit[0]),
                          "global_index": k * n + int(hit[0])})
    if most != worst["opponent"]:
        row = next(r for r in rows if r["opponent"] == most)
        k = row["cell_index"]
        taken = {p["global_index"] for p in picks}
        done = [g for g in np.flatnonzero(out[k * n:(k + 1) * n] != UNFINISHED) if k * n + int(g) not in taken]
        if done:
            picks.append({"pick": "most_met", "opponent": most, "cell_index": k, "game_index": int(done[0]),
                          "global_index": k * n + int(done[0])})
    return picks


# ============================================================================================ the replay
def build_team(d: dict, device: str):
    """The run's trained team through the route's loader, as the driver's evaluation played it."""
    import torch

    from svg_training.ste import exploit, exploit_train, skills

    gates, side, variant = d["gates"], d["side"], d["variant"]
    saved = torch.load(d["run"] / "agent_final.pt", map_location=device, weights_only=False)
    hidden = list(gates.trainer["hidden"])
    try:
        if gates.learner.skills:            # the driver's DecisionEnv dispatch (build_learner -> decision_env)
            settings = exploit.side_settings(gates, side, None, variant)
            cfg = exploit.train_cfg(gates, variant)
            if settings["shaping_weight"] != cfg.rewards.shaping_weight:
                cfg = cfg.replace(**{"rewards.shaping_weight": float(settings["shaping_weight"])})
            dispatch = skills.two_level_dispatch(gates.learner, gates.players, side, cfg,
                                                 int(gates.trainer["num_games"]), device,
                                                 int(gates.variants[variant]["train_seed"][side]))
            return exploit_train.skill_team_from_modules(side, saved, hidden, dispatch, device)
        return exploit_train.team_from_modules(side, saved, hidden, device)
    except ValueError as err:
        raise Refused(f"{d['run']}/agent_final.pt: the route's loader refuses it: {err}") from err


def capture(d: dict, picks: list[dict], out: Path, commit: str) -> tuple[list[dict], dict]:
    """Replay the INFO batch on the run's device, check each pick against the record, save the equal ones
    (``<out>/trajectories/<stem>.npz``). Returns (picks with their check and file, the batch's check)."""
    import torch

    import ste_exploit_l012 as driver
    from svg_training.ste import exploit, sweep
    from svg_training.viz import replay3d as r3

    gates, side, variant = d["gates"], d["side"], d["variant"]
    device = str(gates.run["device"])
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise Refused(f"the run was evaluated on {device}; no CUDA here (a CPU replay cannot be checked game for game "
                      f"against a CUDA record)")
    missing = [k for k in r3.EXACT_KEYS if k not in d["info"]]
    if missing:
        raise Refused(f"eval_info.npz has no {missing}")
    record = {k: d["info"][k] for k in r3.EXACT_KEYS + r3.CLOSE_KEYS if k in d["info"]}
    cells = driver.info_cells(gates, side)
    n, ticks = int(gates.run["eval_games"]), int(gates.run["ticks_cap"])
    ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
    cfg = exploit.variant_cfg(gates, variant)
    team = build_team(d, device)
    hold = int(gates.trainer["decision_ticks"])
    tol = 0.0 if device == "cpu" else float(sweep.load_gates().controls["same_seed_closest_tol_m"])
    started = time.time()
    say(f"replaying the INFO batch ({len(cells)} cells x {n} games) on {device}; key games "
        f"{[p['global_index'] for p in picks]}")
    try:
        cap = r3.capture_trained(cfg, gates.run["size"], ref, cells, n, device, int(ref.meta["seed"]), ticks, team,
                                 hold, [p["global_index"] for p in picks])
    except ValueError as err:
        raise Refused(str(err)) from err
    except RuntimeError as err:                  # a kept game the record finished did not finish in the replay
        for p in picks:
            p["check"] = {"equal": False, "error": str(err)}
        return picks, {"equal": False, "error": str(err), "seconds": round(time.time() - started, 1)}
    batch = r3.check_against_record(cap.per_game, record, tol_m=tol)
    batch.update({"games_compared": int(len(cells) * n), "tol_m": tol, "seconds": round(time.time() - started, 1)})
    say(f"batch check: {'EQUAL' if batch['equal'] else 'DIFFERENT'} {batch['mismatches']} ({batch['seconds']} s)")
    for p, t in zip(picks, cap.trajectories):
        g = p["global_index"]
        p["check"] = r3.check_against_record({k: v[g:g + 1] for k, v in cap.per_game.items()},
                                             {k: v[g:g + 1] for k, v in record.items()}, tol_m=tol)
        p["recorded"] = {"outcome": int(record["outcome"][g]), "end_step": int(record["end_step"][g]),
                         "tags": int(record["tags"][g])}
        p["replayed"] = {"outcome": int(cap.per_game["outcome"][g]), "end_step": int(cap.per_game["end_step"][g]),
                         "tags": int(cap.per_game["tags"][g])}
        if not p["check"]["equal"]:
            say(f"  {p['pick']}: game {p['game_index']} v {p['opponent']} DIFFERS from the record "
                f"{p['check']['mismatches']}: not drawn")
            continue
        p["stem"] = f"{variant}_{side}_{p['pick']}_{p['opponent']}_game{p['game_index']}"
        trained = f"trained {side.capitalize()} team"
        t.meta.update({"kind": "l5_trained", "task": gates.run["task"], "run": d["run"].name, "variant": variant,
                       "side": side, "pick": p["pick"], "opponent": p["opponent"],
                       "guard": trained if side == "guard" else p["opponent"],
                       "strike": trained if side == "strike" else p["opponent"],
                       "outcome_name": "reach" if t.outcome == exploit.STRIKE_WIN else "hold",
                       "trained_team_won": t.outcome == won_code(side), "game_index": p["game_index"],
                       "cell_index": p["cell_index"], "games_per_cell": n, "tags": int(record["tags"][g]),
                       "device": device, "commit": commit, "gates_sha256": gates.sha256,
                       "route": "skills (two-level)" if gates.learner.skills else "velocity"})
        path = r3.save_trajectory(out / "trajectories" / p["stem"], t)
        p["trajectory"] = str(path.relative_to(out))
        say(f"  {p['pick']}: game {p['game_index']} v {p['opponent']}, {t.meta['outcome_name']} at "
            f"{t.end_time_s:.2f} s -> {path.name}")
    return picks, batch


# ============================================================================================ render and encode
def render_stage(out: Path, work: Path, trajectories: list[Path], settings: str) -> int:
    """The preflight (--approved-headless --allow-siblings), then ``make_ste_3d.render`` in an Isaac child process
    (headless, cameras on). Returns 0, the preflight's 11, or the child's code."""
    pre = subprocess.run(["bash", str(ROOT / "scripts" / "isaac_preflight.sh"), "--approved-headless",
                          "--allow-siblings"], capture_output=True, text=True)
    work.mkdir(parents=True, exist_ok=True)
    (work / "preflight.txt").write_text(pre.stdout + pre.stderr)
    say(f"preflight exit {pre.returncode}")
    if pre.returncode != 0:
        print(pre.stdout[-1500:], flush=True)
        return EXIT_GPU_BUSY if pre.returncode == 11 else EXIT_RENDER
    cmd = [sys.executable, str(Path(__file__).resolve()), "--render-child", "--work", str(work), "--settings",
           settings, "--replay", *[str(p) for p in trajectories], "--headless"]
    return subprocess.run(cmd, cwd=str(ROOT)).returncode


def render_child() -> int:
    """Isaac side (the child process): ``make_ste_3d.render`` on the trajectories; leaves with os._exit."""
    import make_ste_3d as m3
    from _isaac_app import start_headless

    ap = m3.make_parser()
    ap.add_argument("--render-child", action="store_true")
    args, _app = start_headless(ap, cameras=True)
    code = EXIT_RENDER
    try:
        from svg_training.compat import isaaclab_232 as isaac
        code = m3.render(args, isaac)
    except BaseException:
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)


def encode_clips(out: Path, work: Path, settings_file: str) -> dict:
    """From ``<work>/render_meta.json`` and the raw frames: the VID-1 overlay (caption, legend, banner at the end, info
    line, clock) and the tag crosses, MP4 and GIF per camera into ``<out>``. Returns {stem: {camera: files}}."""
    import imageio.v2 as imageio

    import make_ste_3d as m3
    from svg_training.bench.overlay import draw_overlay, encode_mp4
    from svg_training.viz import replay3d as r3
    from svg_training.viz.starling_look import load_video_settings

    pb = load_video_settings(settings_file)["playback"]
    meta = json.loads((work / "render_meta.json").read_text())
    res = tuple(meta["resolution"])
    fps = r3.playback_fps(float(pb["speed_x"]))
    done = {}
    for rec in meta["replays"]:
        t = r3.load_trajectory(rec["trajectory_path"])
        m = t.meta
        result = r3.outcome_text(t.outcome, t.end_step, int(m["tags"]), int(t.alive[-1, :t.guards].sum()))
        cap = r3.caption(m["variant"], float(pb["speed_x"]),
                         source=f"the {m['task']} run's evaluation, {m['route']} route, trained "
                                f"{m['side'].capitalize()} team")
        files = {}
        for cam in m3.CAMERAS:
            info = (r3.info_line(m["variant"], t.guards, t.strikes, m["guard"], m["strike"], int(m["game_index"]),
                                 2 * t.half_m) + f" | {m['pick'].replace('_', ' ')} | {m3.CAMERA_NAMES[cam]}")
            view = rec["cameras"][cam]
            reader = imageio.get_reader(str(work / "render" / rec["stem"] / f"raw_{cam}.mp4"))
            raw = [img for img in reader]          # list(reader) asks len(): inf for a video
            reader.close()
            if len(raw) != rec["frames"]:
                raise RuntimeError(f"{rec['stem']} {cam}: {len(raw)} raw frames, expected {rec['frames']}")
            frames = []
            for k, img in enumerate(raw):
                img = m3.draw_tag_crosses(img, t, k, view["eye"], view["lookat"], res)
                frames.append(draw_overlay(img, cap, m3.LEGEND_3D, 0.0, result if k == len(raw) - 1 else None, info,
                                           clock=f"t = {k * 0.05:4.2f} s"))
            frames += [frames[-1]] * r3.hold_frames(float(pb["hold_s"]), fps)
            stem = f"{rec['stem']}_{cam}"
            mp4, crf = encode_mp4(frames, out / f"{stem}.mp4", fps=fps, max_mb=float(pb["mp4_max_mb"]))
            gif, gi = m3.gif_full_rate(frames, out / f"{stem}.gif", fps, float(pb["gif_max_mb"]))
            shots = work / "render" / rec["stem"]
            imageio.imwrite(str(shots / f"overlay_{cam}_last.png"), frames[len(raw) - 1])
            files[cam] = {"mp4": mp4.name, "mp4_mb": round(mp4.stat().st_size / 1e6, 2), "crf": crf,
                          "gif": gi | {"file": gif.name, "mb": round(gif.stat().st_size / 1e6, 2)}}
        done[rec["stem"]] = {"files": files, "result": result, "caption": cap}
        say(f"encoded {rec['stem']}: " + ", ".join(f"{c} {f['gif']['file']} ({f['gif']['mb']} MB)"
                                                    for c, f in files.items()))
    return done


# ============================================================================================ main
def parse(argv):
    ap = argparse.ArgumentParser(prog="ste_l5_clips3d.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-dir", type=Path, required=True, help="the finished L5 run folder (read only)")
    ap.add_argument("--out", type=Path, default=None, help=f"the clips' folder (default <run>/{DEFAULT_OUT})")
    ap.add_argument("--settings", default=None, help="the video settings (default configs/ste_video.toml)")
    ap.add_argument("--plan-only", action="store_true", help="the checks and the picks only; writes nothing")
    return ap.parse_args(argv)


def git_commit() -> str:
    r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


def write_report(out: Path, report: dict) -> None:
    from svg_training.ste import atomic
    atomic.write_text(out / CLIPS_JSON, json.dumps(report, indent=1))


def plan(d: dict) -> dict:
    rows = info_table(d)
    worst = worst_cell(rows)
    meet = training_meetings(d)
    picks = pick_games(d, rows, worst, meet["most"])
    return {"cells": rows, "worst": worst["opponent"], "training": meet, "picks": picks}


def main(argv=None) -> int:
    a = parse(argv)
    from svg_training.viz.starling_look import SETTINGS_FILE

    settings = a.settings or str(SETTINGS_FILE)
    run = a.run_dir.resolve()
    out = (a.out or run / DEFAULT_OUT).resolve()
    if not a.plan_only and out != run / DEFAULT_OUT and run in out.parents:
        say(f"refused: --out {out} is inside the run folder but not {run / DEFAULT_OUT}")
        return EXIT_REFUSED
    try:
        d = load_run(run)
        p = plan(d)
    except Refused as err:
        say(f"refused: {err}")
        return EXIT_REFUSED
    gates = d["gates"]
    say(f"{run.name}: task {gates.run['task']}, {d['variant']}, trained {d['side']}, "
        f"{'skills (two-level)' if gates.learner.skills else 'velocity'} route")
    for r in p["cells"]:
        say(f"  {r['cell']}: won {r['wins']}, lost {r['losses']}, unfinished {r['unfinished']} of {r['games']}"
            f"{' (z_up_info)' if r['z_up_info'] else ''}")
    say(f"worst cell: v {p['worst']}; met most in training: {p['training']['most']} {p['training'].get('counts')}")
    say("picks: " + "; ".join(f"{x['pick']} v {x['opponent']} game {x['game_index']}" for x in p["picks"]))
    if a.plan_only:
        return EXIT_DONE
    if (out / CLIPS_JSON).is_file() and json.loads((out / CLIPS_JSON).read_text()).get("complete") is True:
        say(f"refused: {out / CLIPS_JSON} is complete already: new clips need a new folder")
        return EXIT_REFUSED
    out.mkdir(parents=True, exist_ok=True)
    (out / CLIPS_JSON).unlink(missing_ok=True)
    for stale in list((out / "trajectories").glob("*")) if (out / "trajectories").is_dir() else []:
        stale.unlink()                           # never leave an earlier launch's game to be drawn
    commit = git_commit()
    report = {"what": "STE L5: 3-D Isaac Lab clips of a finished run's key games (scripts/ste_l5_clips3d.py); "
                      "observed in the training simulator, not a flight",
              "run": str(run), "task": gates.run["task"], "variant": d["variant"], "side": d["side"],
              "route": "skills (two-level)" if gates.learner.skills else "velocity", "gates_sha256": gates.sha256,
              "device": str(gates.run["device"]), "commit": commit, "rule": RULE, **p, "complete": False}
    started = time.time()
    try:
        picks, batch = capture(d, p["picks"], out, commit)
    except Refused as err:
        say(f"refused: {err}")
        report["refused"] = str(err)
        write_report(out, report)
        return EXIT_REFUSED
    report.update({"picks": picks, "batch_check": batch, "capture_s": round(time.time() - started, 1)})
    code = EXIT_DONE if all(x["check"]["equal"] for x in picks) else EXIT_MISMATCH
    drawn = [out / x["trajectory"] for x in picks if "trajectory" in x]
    write_report(out, report)                    # complete: false until the clips are made
    if drawn:
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:                        # noqa: BLE001  (best effort: the render's memory)
            pass
        work = out / "work"
        t0 = time.time()
        rc = render_stage(out, work, drawn, settings)
        report["render"] = {"exit": rc, "seconds": round(time.time() - t0, 1)}
        if rc != 0:
            say(f"render failed (exit {rc}); nothing encoded")
            write_report(out, report)
            return EXIT_GPU_BUSY if rc == EXIT_GPU_BUSY else EXIT_RENDER
        try:
            enc = encode_clips(out, work, settings)
        except Exception as err:                 # noqa: BLE001  (recorded, exit 3)
            traceback.print_exc()
            report["encode_error"] = repr(err)
            write_report(out, report)
            return EXIT_RENDER
        for x in picks:
            if x.get("stem") in enc:
                x.update(enc[x["stem"]])
        render_meta = json.loads((work / "render_meta.json").read_text())
        report["render"].update({k: render_meta.get(k) for k in ("isaac", "starling_usd", "starling_usd_sha256",
                                                                   "settings_file", "settings_sha256", "working_tree",
                                                                   "resolution")})
    else:
        report["render"] = {"exit": None, "note": "no picked game equals the record: nothing drawn"}
    report["picks"] = picks
    report["complete"] = True                    # written last
    write_report(out, report)
    say(f"{CLIPS_JSON} written ({len(drawn)} of {len(picks)} games drawn); exit {code}")
    return code


if __name__ == "__main__":
    if "--render-child" in sys.argv[1:]:
        sys.exit(render_child())
    sys.exit(main())
