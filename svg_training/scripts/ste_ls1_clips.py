#!/usr/bin/env python
"""STE route 3, stage LS1, job LS1.6: 3-D Isaac Lab clips of the copy beside the scripts (plan
ste_learning/drafts/LS1_TASK_PLAN.md, task LS1-M3-T6, and the design check of M3). A few games of a finished
equivalence read (job LS1.2, ``scripts/ste_ls1_equivalence.py``) are played again, each twice: once flown by the skill
network (the copy, the read's R1 batch) and once by the scripts (the read's C1 or C1m batch, the same start), and both
are drawn, to be shown side by side on the record page (OP-38). Nothing is written in a read folder.

    ste_ls1_clips.py --equivalence <read folder> [--equivalence <read folder>] --out <folder>
                     [--skill-net <file> ...] [--settings configs/ste_video.toml] [--picks-per-side N] [--plan-only]

Launch: ``scripts/ste_job.py launch --task LS1.6 --gpu-h <the ask --plan-only prints> --run-dir <out> ... -- <this
command>`` after ``nvidia-smi``; the render stage runs ``scripts/isaac_preflight.sh --approved-headless
--allow-siblings`` itself (``ste_l5_clips3d.render_stage``). ``--plan-only`` (CPU) prints the picks, the GPU-hour ask,
the number of batch replays and their CPU estimate, the ask at each pick count, and writes nothing.

**The read, rebuilt** (all read only): the read folder's ``run.json``, ``results.json`` (complete, with cells),
``layout.json`` (every batch played), ``gates.toml`` (the pinned copy: its sha256 = ``gates.sha256`` = results' and
run.json's), ``games/<batch>.npz``. The read's own context is rebuilt by the read's own code (``eq.parse`` and
``eq.prepare`` on run.json's side, smoke, chunk and test-only options, the pinned gate copy and the network file), so
every pin the read checks is checked again; then ``eq.plan_batches`` must give the very layout of ``layout.json``
(``eq.layout_problem``). The network file: run.json's ``skill_net_file`` when it lies inside ``svg_training/``, else a
``--skill-net`` file with the read's ``net_sha256`` (a network outside the repository, a test's ``tmp_path``). The read
is a CPU job (``eq.prepare`` refuses a cuda ``[read] device``), so the replays run on the CPU inside this job; a CUDA
record on a machine without CUDA is refused all the same (``ste_l5_clips3d.py``'s rule).

**The picks** (:data:`RULE`, fixed in this code before anything is rendered; OP-27 as the lead settled it, OQ-4):
see RULE. ``--picks-per-side`` N (default 3, at least ``MIN_PICKS_PER_SIDE`` = 2) keeps the first N picks of each
side's order; above 3 the extra picks are more agreeing games (the fill). The ask (:func:`estimate`): ``ste_l5_clips3d``'s
cost constants for the render and the encode of every trajectory (two per pick), plus the read's own ``layout.json``
seconds of every batch replayed (the replays run inside this job: they are in the ask, and printed on a line of their
own), times ``ASK_MARGIN``. Above the LS1.6 cap (``configs/ste_learning.toml [budget_ls.task_cap_gpu_h]``, read, not
typed) the picks per side fall one at a time (the fill first, then the fixed cell's c game) down to
``MIN_PICKS_PER_SIDE``; above the cap even there: refused (exit 2), nothing launched, the lead decides (R39, OQ-4).

**The replays** (B-11): one replay per batch for every picked game in it (``viz/replay3d.capture_trained``'s ``keep``),
so a batch is never replayed twice; the batch is rebuilt whole, as the read played it (``eq.arms`` builds its players
and ``cells.cell_of`` its pairs, ``eq.play_batch``'s two lines; hold ``eq.HOLD_TICKS``; T44's starts; the batch-mates
matter, ``ste/sweep.py``). Each replayed game is checked against the read's own per-game record (outcome, end step,
tags, Strike drones left, start positions exactly; closest approach within 0 on the CPU): a pick is drawn only if both
of its arms equal the record; otherwise neither is drawn and the job exits 1.

**Drawn**: trajectories ``<out>/trajectories/<side>_<pick>_cell<index>_game<i>_<copy|scripts>.npz`` (meta: kind, side,
arm, pick, cell, codes, opponent, game index, outcome, tags, pair class, device, commit, the gate file's and the
network's sha256, the read); one render launch for both sides (``l5.render_stage``: Isaac, headless, two cameras);
this script's own encode (:func:`encode_ls1`, from ``ste_l5_clips3d``'s helpers: MP4 of every tick, GIF time-compressed
to fit); ``<out>/clips_ls1.json`` (the reads, the rule, the picks with both arms' checks and files, the replays, the
estimate, the games drawn per side; ``complete: true`` written last). Visual tooling: no gate, no verdict.

Exit codes: 0 done; 1 a replayed game differs from the read (that pick not drawn; the others are); 2 refused (a read
file missing or inconsistent, a side twice, no mixed cell, picks below the minimum, the ask above the cap, ``--out``
inside a read folder or finished); 3 the render failed or no clip was encoded; 11 the GPU is busy (the preflight's
code). Tier 1; observed in the training simulator; not a flight."""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import torch  # noqa: E402

import ste_l5_clips3d as l5  # noqa: E402
import ste_ls1_equivalence as eq  # noqa: E402
from svg_training.ste import atomic, cells, config, exploit, sweep  # noqa: E402
from svg_training.viz import replay3d as r3  # noqa: E402

TASK = "LS1.6"
TAG = "[ls1.6 clips]"
EXIT_DONE, EXIT_MISMATCH, EXIT_REFUSED, EXIT_RENDER, EXIT_GPU_BUSY = (l5.EXIT_DONE, l5.EXIT_MISMATCH, l5.EXIT_REFUSED,
                                                                      l5.EXIT_RENDER, l5.EXIT_GPU_BUSY)
CLIPS_JSON = "clips_ls1.json"
TRAJ_DIR = "trajectories"
MIN_PICKS_PER_SIDE = 2               # R2 RC-5, OA-8: one fixed-cell and one mixed-cell game per side, both arms each
DEFAULT_PICKS_PER_SIDE = 3           # OP-27: filled to 3 per side
COPY, SCRIPTS = "copy", "scripts"    # the two arms of a pick: the skill network (R1), the scripts (C1 or C1m)
ARMS = (COPY, SCRIPTS)
PICK_FIXED_B, PICK_MIXED, PICK_FIXED_C, PICK_FILL = "fixed_b", "mixed_changed", "fixed_c", "fill"
GATED_KINDS = (cells.FIXED, cells.MIXED)
CAMERAS = 2                          # make_ste_3d.CAMERAS: top view and 3-D view
HOLD_FRAMES = 20                     # the end frame held, per clip (ste_l5_clips3d.estimate's default)
RULE = ("Fixed in scripts/ste_ls1_clips.py before rendering (OP-27 as the lead settled it; OQ-4). Per side, from the "
        "read's results.json cells of the network's arm (arm net) and kind fixed or mixed only (info cells and every "
        "other arm left out): the fixed cell with the most flips and the mixed cell with the most flips, a tie to the "
        "lowest cell index; no mixed cell: refused. Each game's class is the read's pair_class (b: the scripts won, "
        "the copy lost; c: the reverse; agreeing). The picks, in this order: (1) the fixed cell's lowest b game; (2) "
        "the mixed cell's lowest changed game (b or c); (3) the fixed cell's lowest c game; (4 on) the fill: agreeing "
        "games, the fixed cell's then the mixed cell's, lowest first. A slot with no such game takes its cell's lowest "
        "agreeing game not picked, else its lowest game not picked; no game is picked twice. --picks-per-side N "
        "(default 3, at least MIN_PICKS_PER_SIDE = 2) keeps the first N of each side; above 3, more fill. Above the "
        "LS1.6 cap the picks per side fall one at a time (the fill first, then the fixed cell's c game), never below "
        "MIN_PICKS_PER_SIDE; above the cap there: refused. Each pick is drawn twice, flown by the copy (the read's R1 "
        "batch) and by the scripts (the cell's C1 or C1m batch, the same start), only if both replays equal the "
        "read's record (outcome, end step, tags, Strike drones left, start positions; closest approach within 0 on "
        "the CPU); otherwise neither is drawn.")


def say(text: str) -> None:
    print(f"{TAG} {text}", flush=True)


class Refused(Exception):
    """Bad input: exit 2, nothing drawn."""


# ============================================================================================ reading a read
@dataclass
class Read:
    """A finished equivalence read, rebuilt by the read's own code: its folder, side, context (``eq.Ctx``), batches
    (``eq.plan_batches``, by name), ``layout.json`` entries by name, ``results.json``, reader and network file."""
    folder: Path
    side: str
    ctx: object
    batches: dict
    layout: dict
    results: dict
    reader: object
    net_file: Path

    @property
    def name(self) -> str:
        return eq.rel(self.folder)


def device_check(device: str) -> None:
    """Refused for a CUDA record on a machine without CUDA (``ste_l5_clips3d.py``'s rule: a CPU replay cannot be
    checked game for game against a CUDA record)."""
    if str(device).startswith("cuda") and not torch.cuda.is_available():
        raise Refused(f"the read was played on {device}; no CUDA here (a CPU replay cannot be checked game for game "
                      f"against a CUDA record)")
    return None


def _json(path: Path) -> dict:
    if not path.is_file():
        raise Refused(f"{eq.rel(path)} is missing (not a finished equivalence read)")
    return json.loads(path.read_text())


def _net_file(folder: Path, run: dict, net_sha: str, given: list[Path]) -> Path:
    """The read's network file: run.json's repository-relative ``skill_net_file``, else a ``--skill-net`` file with
    the read's network sha256."""
    named = ROOT / str(run.get("skill_net_file", ""))
    if named.is_file() and exploit.sha256_file(named) == net_sha:
        return named
    for path in given:
        if Path(path).is_file() and exploit.sha256_file(path) == net_sha:
            return Path(path).resolve()
    raise Refused(f"{eq.rel(folder)}: no network file with sha256 {net_sha} (run.json names "
                  f"{run.get('skill_net_file')!r}; give it with --skill-net)")


def _read_argv(folder: Path, run: dict, net: Path) -> list[str]:
    argv = ["--gates", str(folder / eq.GATES_COPY), "--side", str(run["side"]), "--skill-net", str(net), "--run-dir",
            str(folder), "--cap-h", "1", "--chunk", str(int(run["chunk_cells"]))]
    if run.get("smoke"):
        argv.append("--smoke")
    over = run.get("overrides") or {}
    if "games" in over:
        argv += ["--games", str(int(over["games"]))]
    if "opponents" in over:
        argv += ["--opponents", *[str(o) for o in over["opponents"]]]
    if "mixed" in over:
        argv += ["--mixed", str(int(over["mixed"]))]
    return argv


def load_read(folder: Path, given: list[Path]) -> Read:
    """A finished read, its pins checked and its context rebuilt by ``eq.prepare`` (Refused names the first problem)."""
    folder = Path(folder).resolve()
    run, res, layout = _json(folder / eq.RUN_FILE), _json(folder / eq.RESULTS), _json(folder / eq.LAYOUT_FILE)
    if res.get("complete") is not True:
        raise Refused(f"{eq.rel(folder)}/{eq.RESULTS} is not complete")
    if not res.get("cells"):
        raise Refused(f"{eq.rel(folder)}: results.json has no cells (verdict {res.get('verdict')!r}: no result batch)")
    pinned = (folder / eq.PINNED_SHA).read_text().strip() if (folder / eq.PINNED_SHA).is_file() else None
    copy_sha = exploit.sha256_file(folder / eq.GATES_COPY) if (folder / eq.GATES_COPY).is_file() else None
    if not (copy_sha == pinned == res.get("gates_sha256") == run.get("gates_sha256")) or copy_sha is None:
        raise Refused(f"{eq.rel(folder)}: the gate file copy {copy_sha}, the pin {pinned}, results.json "
                      f"{res.get('gates_sha256')} and run.json {run.get('gates_sha256')} are not one gate file")
    net_sha = res.get("net_sha256")
    if not net_sha or net_sha != run.get("net_sha256"):
        raise Refused(f"{eq.rel(folder)}: results.json names the network {net_sha}, run.json {run.get('net_sha256')}")
    net = _net_file(folder, run, net_sha, given)
    args = eq.parse(_read_argv(folder, run, net))
    ctx, why = eq.prepare(args)
    if why:
        raise Refused(f"{eq.rel(folder)}: the read's own checks refuse it: {why}")
    if ctx.net_sha != net_sha or ctx.g.sha256 != copy_sha or ctx.n != int(run["games_per_cell"]) or \
            ctx.side != run["side"]:
        raise Refused(f"{eq.rel(folder)}: the rebuilt read (network {ctx.net_sha}, gate file {ctx.g.sha256}, "
                      f"{ctx.n} games, {ctx.side}) is not the recorded one")
    batches = eq.plan_batches(ctx)
    problem = eq.layout_problem(ctx, batches)
    if problem:
        raise Refused(f"{eq.rel(folder)}: {problem}")
    entries = layout.get("batches", [])
    if len(entries) != len(batches) or any(e.get("seconds") is None for e in entries):
        raise Refused(f"{eq.rel(folder)}/{eq.LAYOUT_FILE}: {len(entries)} of {len(batches)} batches, not every one "
                      f"played: the read has not finished")
    for e in entries:
        device_check(e["device"])
    return Read(folder=folder, side=ctx.side, ctx=ctx, batches={b.name: b for b in batches},
                layout={e["name"]: e for e in entries}, results=res, reader=eq.Reader(ctx, batches), net_file=net)


# ============================================================================================ the picks
def _first(cell: dict, wanted, taken: set) -> int | None:
    for g in np.flatnonzero(np.isin(cell["classes"], list(wanted))):
        if (cell["index"], int(g)) not in taken:
            return int(g)
    return None


def side_picks(rows: list[dict], count: int) -> list[dict]:
    """:data:`RULE` on one side's cells. ``rows``: [{"index" (the cell's index in the side's list), "kind", "arm",
    "flips", "classes" [n] int8 (pair_class of the cell's games)}]. Returns the first ``count`` picks in the rule's
    order, each {"pick", "cell", "game", "class"}; Refused when the network has no fixed or no mixed cell."""
    mine = [r for r in rows if r["arm"] == eq.NET and r["kind"] in GATED_KINDS]
    fixed = [r for r in mine if r["kind"] == cells.FIXED]
    mixed = [r for r in mine if r["kind"] == cells.MIXED]
    if not fixed:
        raise Refused("the network has no fixed cell in this read: no fixed-cell pick")
    if not mixed:
        raise Refused("the network has no mixed cell in this read (--mixed 0?): no mixed-cell pick (RULE)")
    f = min(fixed, key=lambda r: (-int(r["flips"]), int(r["index"])))
    x = min(mixed, key=lambda r: (-int(r["flips"]), int(r["index"])))
    taken, out = set(), []

    def add(name: str, cell: dict, wanted) -> None:
        g = _first(cell, wanted, taken)
        if g is None:
            g = _first(cell, (eq.PAIR_SAME,), taken)
        if g is None:
            g = _first(cell, (eq.PAIR_SAME, eq.PAIR_B, eq.PAIR_C), taken)
        if g is not None:
            taken.add((cell["index"], g))
            out.append({"pick": name, "cell": int(cell["index"]), "game": g, "class": int(cell["classes"][g])})

    add(PICK_FIXED_B, f, (eq.PAIR_B,))
    add(PICK_MIXED, x, (eq.PAIR_B, eq.PAIR_C))
    add(PICK_FIXED_C, f, (eq.PAIR_C,))
    while len(out) < count:
        cell = next((c for c in (f, x) if _first(c, (eq.PAIR_SAME,), taken) is not None), None)
        if cell is None:
            break
        g = _first(cell, (eq.PAIR_SAME,), taken)
        taken.add((cell["index"], g))
        out.append({"pick": PICK_FILL, "cell": int(cell["index"]), "game": g, "class": int(cell["classes"][g])})
    return out[:count]


def _layout_cell(read: Read, row: dict) -> tuple[str, int, dict]:
    """(batch name, place in the batch, layout cell) of a results.json cell (its games' start // n)."""
    entry = read.layout.get(row["batch"])
    if entry is None or row["games"]["file"] != f"{eq.GAMES_DIR}/{row['batch']}.npz":
        raise Refused(f"{read.name}: results.json cell of batch {row['batch']!r} is not in layout.json")
    place = int(row["games"]["start"]) // read.ctx.n
    lc = entry["cells"][place]
    if (list(lc["codes"]), lc["opponent"]) != (list(row["codes"]), row["opponent"]):
        raise Refused(f"{read.name}: results.json cell {row['codes']}@{row['opponent']} is not layout.json's cell "
                      f"{place} of {row['batch']}")
    return row["batch"], place, lc


def read_rows(read: Read) -> list[dict]:
    """The read's results.json cells as :func:`side_picks` rows (the network's gated cells carry their pair_class
    from their batch file)."""
    rows = []
    for row in read.results["cells"]:
        out = {"index": None, "kind": row["kind"], "arm": row["arm"], "flips": int(row["flips"]), "classes": None,
               "row": row}
        if row["arm"] == eq.NET and row["kind"] in GATED_KINDS:
            batch, place, lc = _layout_cell(read, row)
            pg = read.reader.load(read.batches[batch])
            if "pair_class" not in pg:
                raise Refused(f"{read.name}: {batch} has no pair_class")
            out["index"] = int(lc["index"])
            out["classes"] = np.asarray(pg["pair_class"][row["games"]["start"]:row["games"]["stop"]])
        rows.append(out)
    return rows


def plan(reads: list[Read], count: int) -> dict:
    """The picks of every read at ``count`` per side, both arms of each located in the read's batches, the replays
    (one per batch) and the estimate."""
    picks, replays = [], {}
    for read in reads:
        rows = read_rows(read)
        by_index = {r["index"]: r for r in rows if r["index"] is not None}
        for p in side_picks(rows, count):
            row = by_index[p["cell"]]["row"]
            batch, place, _ = _layout_cell(read, row)
            ref_batch, ref_place = read.reader.where[("gated", p["cell"])]
            n = read.ctx.n
            arms = {COPY: {"batch": batch, "global_index": place * n + p["game"]},
                    SCRIPTS: {"batch": ref_batch.name, "global_index": ref_place * n + p["game"]}}
            for a in arms.values():
                pg = read.reader.load(read.batches[a["batch"]])
                g = a["global_index"]
                a["recorded"] = {"outcome": int(pg["outcome"][g]), "end_step": int(pg["end_step"][g]),
                                 "tags": int(pg["tags"][g])}
                key = (read.side, a["batch"])
                replays.setdefault(key, {"read": read.name, "side": read.side, "batch": a["batch"],
                                         "arm": read.batches[a["batch"]].arm, "keep": set(),
                                         "seconds": float(read.layout[a["batch"]]["seconds"])})["keep"].add(g)
            picks.append({**p, "side": read.side, "read": read.name, "kind": row["kind"], "codes": list(row["codes"]),
                          "opponent": row["opponent"], "net_sha256": read.ctx.net_sha, "arms": arms})
    rep = [{**r, "keep": sorted(r["keep"])} for r in replays.values()]
    return {"picks": picks, "replays": rep, "estimate": estimate(picks, rep)}


def estimate(picks: list[dict], replays: list[dict]) -> dict:
    """The job's expected seconds and GPU-hour ask: ``ste_l5_clips3d``'s cost constants for the render (per tick and
    camera, per trajectory and camera) and the encode of every trajectory (two per pick), plus the read's own seconds
    of every batch replayed (``layout.json``: the replays run inside this job), times ``ASK_MARGIN``."""
    ticks = sum(a["recorded"]["end_step"] + 1 for p in picks for a in p["arms"].values())
    trajectories = 2 * len(picks)
    replay_s = float(sum(r["seconds"] for r in replays))
    seconds = (l5.FIXED_S + replay_s
               + CAMERAS * (l5.RENDER_S_PER_TICK_CAMERA * ticks + l5.RENDER_S_PER_GAME_CAMERA * trajectories)
               + CAMERAS * l5.ENCODE_S_PER_FRAME * (ticks + HOLD_FRAMES * trajectories))
    ask = float(math.ceil(l5.ASK_MARGIN * seconds / eq.HOUR_S * 100) / 100)
    return {"trajectories": trajectories, "ticks_to_render": ticks, "batch_replays": len(replays),
            "replay_cpu_s": replay_s, "expected_s": round(seconds, 1), "ask_gpu_h": ask,
            "costs": {"render_s_per_tick_camera": l5.RENDER_S_PER_TICK_CAMERA,
                      "render_s_per_game_camera": l5.RENDER_S_PER_GAME_CAMERA,
                      "encode_s_per_frame": l5.ENCODE_S_PER_FRAME, "fixed_s": l5.FIXED_S, "margin": l5.ASK_MARGIN,
                      "replay": "the read's layout.json seconds of each batch replayed"}}


def fit_to_cap(count: int, cap: float, ask_of) -> tuple[int, dict, bool]:
    """(picks per side, its estimate, fits): ``count`` lowered one at a time while ``ask_of(count)["ask_gpu_h"]`` is
    above ``cap``, never below ``MIN_PICKS_PER_SIDE``."""
    est = ask_of(count)
    while est["ask_gpu_h"] > cap and count > MIN_PICKS_PER_SIDE:
        count -= 1
        est = ask_of(count)
    return count, est, est["ask_gpu_h"] <= cap


def task_cap_gpu_h() -> float:
    """The LS1.6 cap of ``configs/ste_learning.toml`` (the lead's, under R39)."""
    return float(config.load_ste_learning(config.SETTINGS_FILE)[0].cap_gpu_h(TASK))


# ============================================================================================ the replays
def replay(read: Read, batch_name: str, keep: list[int]):
    """The read's batch ``batch_name`` played again whole, as ``eq.play_batch`` plays it (its players from
    ``eq.arms``, its pairs from ``cells.cell_of``, hold ``eq.HOLD_TICKS``), keeping every step of the games ``keep``."""
    ctx, batch = read.ctx, read.batches[batch_name]
    net = ctx.net if batch.arm in (eq.NET, eq.PERMUTED) else None
    players = eq.arms(ctx.side, batch.arm, g=ctx.g, among=batch.cells, cfg=ctx.cfg, n=ctx.n, device=ctx.device,
                      seed=ctx.seed, net=net, net_sha256=ctx.net_sha if net is not None else None)
    pairs = [cells.cell_of(ctx.side, name, cell.opponent) for name, cell in zip(players, batch.cells)]
    return r3.capture_trained(ctx.cfg, ctx.g.skills_gates.run["size"], ctx.ref, pairs, ctx.n, ctx.device, ctx.seed,
                              ctx.ticks, None, eq.HOLD_TICKS, list(keep), players=players)


def _record(pg: dict) -> dict:
    return {k: pg[k] for k in r3.EXACT_KEYS + r3.CLOSE_KEYS if k in pg}


def capture(reads: list[Read], p: dict, out: Path, commit: str) -> int:
    """Every replay of the plan (one per batch), each pick's two arms checked against the read's record and, when both
    are equal, saved (``<out>/trajectories``). Fills ``p``'s picks and replays in place; returns the exit code so far."""
    by_side = {r.side: r for r in reads}
    caps = {}
    for rp in p["replays"]:
        read = by_side[rp["side"]]
        record = _record(read.reader.load(read.batches[rp["batch"]]))
        tol = 0.0 if read.ctx.device == "cpu" else float(sweep.load_gates().controls["same_seed_closest_tol_m"])
        started = time.time()
        try:
            cap = replay(read, rp["batch"], rp["keep"])
        except ValueError as err:
            raise Refused(f"{read.name} {rp['batch']}: {err}") from err
        except RuntimeError as err:          # a kept game the read finished did not finish in the replay
            rp.update({"check": {"equal": False, "error": str(err)}, "replay_s": round(time.time() - started, 2)})
            caps[(rp["side"], rp["batch"])] = None
            say(f"{rp['side']} {rp['batch']}: {err}")
            continue
        check = r3.check_against_record(cap.per_game, record, tol_m=tol)
        rp.update({"check": check, "tol_m": tol, "replay_s": round(time.time() - started, 2)})
        caps[(rp["side"], rp["batch"])] = (cap, record, tol, dict(zip(rp["keep"], cap.trajectories)))
        say(f"{rp['side']} {rp['batch']}: {'EQUAL' if check['equal'] else 'DIFFERENT'} {check['mismatches']} "
            f"({rp['replay_s']} s, keep {rp['keep']})")
    code = EXIT_DONE
    for pick in p["picks"]:
        read = by_side[pick["side"]]
        for arm, a in pick["arms"].items():
            got = caps[(pick["side"], a["batch"])]
            if got is None:
                a["check"] = {"equal": False, "error": "the batch's replay failed"}
                continue
            cap, record, tol, _ = got
            g = a["global_index"]
            a["check"] = r3.check_against_record({k: v[g:g + 1] for k, v in cap.per_game.items()},
                                                 {k: v[g:g + 1] for k, v in record.items()}, tol_m=tol)
            a["replayed"] = {"outcome": int(cap.per_game["outcome"][g]), "end_step": int(cap.per_game["end_step"][g]),
                             "tags": int(cap.per_game["tags"][g])}
        pick["drawn"] = all(a["check"]["equal"] for a in pick["arms"].values())
        if not pick["drawn"]:
            code = EXIT_MISMATCH
            say(f"{pick['side']} {pick['pick']}: cell {pick['cell']} game {pick['game']} differs from the read "
                f"({ {arm: a['check'] for arm, a in pick['arms'].items()} }): neither arm drawn")
            continue
        for arm, a in pick["arms"].items():
            _, record, _, trajs = caps[(pick["side"], a["batch"])]
            t = trajs[a["global_index"]]
            stem = f"{pick['side']}_{pick['pick']}_cell{pick['cell']}_game{pick['game']}_{arm}"
            mine = (f"copy of {'+'.join(pick['codes'])}" if arm == COPY else "+".join(pick["codes"]))
            t.meta.update({"kind": "ls1_copy_beside_scripts", "task": TASK, "read": read.name, "side": pick["side"],
                           "arm": arm, "flown_by": "the skill network" if arm == COPY else "the scripts",
                           "pick": pick["pick"], "cell": pick["cell"], "cell_kind": pick["kind"],
                           "codes": pick["codes"], "opponent": pick["opponent"], "game_index": pick["game"],
                           "batch": a["batch"], "pair_class": pick["class"], "variant": read.ctx.variant,
                           "outcome_name": "reach" if t.outcome == exploit.STRIKE_WIN else "hold",
                           "tags": int(record["tags"][a["global_index"]]),
                           "guard": mine if pick["side"] == "guard" else pick["opponent"],
                           "strike": mine if pick["side"] == "strike" else pick["opponent"],
                           "device": read.ctx.device, "commit": commit, "gates_sha256": read.ctx.g.sha256,
                           "net_sha256": read.ctx.net_sha})
            path = r3.save_trajectory(out / TRAJ_DIR / stem, t)
            a.update({"stem": stem, "trajectory": str(path.relative_to(out))})
        say(f"{pick['side']} {pick['pick']}: cell {pick['cell']} ({'+'.join(pick['codes'])} v {pick['opponent']}) "
            f"game {pick['game']}: both arms equal the read -> drawn")
    return code


# ============================================================================================ the encode
def encode_ls1(out: Path, work: Path, settings_file: str) -> dict:
    """``ste_l5_clips3d.encode_clips``' steps with this job's captions (no training run): from ``<work>/render_meta.json``
    and the raw frames, per trajectory and camera an MP4 of every tick (streamed, ``l5.stream_mp4``) and a GIF of at
    most ``l5.GIF_FRAME_CAPS[0]`` frames (time-compressed for a long game, its speed in its caption), into ``<out>``. A
    clip that fails is recorded and the rest go on. Returns {stem: {"files", "result", "caption"}}."""
    import imageio.v2 as imageio

    import make_ste_3d as m3
    from svg_training.viz.starling_look import load_video_settings

    pb = load_video_settings(settings_file)["playback"]
    meta = json.loads((work / "render_meta.json").read_text())
    res = tuple(meta["resolution"])
    speed = float(pb["speed_x"])
    fps = r3.playback_fps(speed)
    hold = r3.hold_frames(float(pb["hold_s"]), fps)
    done = {}
    for rec in meta["replays"]:
        stem_dir = work / "render" / rec["stem"]
        entry = {"files": {}}
        try:
            t = r3.load_trajectory(rec["trajectory_path"])
            m = t.meta
            result = r3.outcome_text(t.outcome, t.end_step, int(m["tags"]), int(t.alive[-1, :t.guards].sum()))
            source = f"the LS1.2 read, {m['side'].capitalize()} team flown by {m['flown_by']}"
            entry.update({"result": result, "caption": r3.caption(m["variant"], speed, source=source)})
        except Exception as err:                 # noqa: BLE001  (recorded; the other games go on)
            entry["error"] = repr(err)
            done[rec["stem"]] = entry
            continue
        for cam in m3.CAMERAS:
            info = (r3.info_line(m["variant"], t.guards, t.strikes, m["guard"], m["strike"], int(m["game_index"]),
                                 2 * t.half_m)
                    + f" | {m['pick'].replace('_', ' ')} | {m['arm']} | {m3.CAMERA_NAMES[cam]}")
            view, raw = rec["cameras"][cam], stem_dir / f"raw_{cam}.mp4"
            files = entry["files"].setdefault(cam, {})
            stem = f"{rec['stem']}_{cam}"
            try:
                n_raw = sum(1 for _ in l5._raw_frames(raw))
                if n_raw != rec["frames"]:
                    raise RuntimeError(f"{n_raw} raw frames, expected {rec['frames']}")
                mp4 = out / f"{stem}.mp4"
                crf = l5.stream_mp4(lambda: l5._overlaid(raw, t, view, res, entry["caption"], result, info), mp4, fps,
                                    hold, float(pb["mp4_max_mb"]))
                files.update({"mp4": mp4.name, "mp4_mb": round(mp4.stat().st_size / 1e6, 2), "crf": crf,
                              "mp4_speed_x": speed, "mp4_frames": n_raw + hold})
            except Exception as err:             # noqa: BLE001  (recorded; the GIF and the other clips go on)
                traceback.print_exc()
                files["mp4_error"] = repr(err)
                say(f"{stem}.mp4 FAILED: {err!r}")
            try:
                gif, tried = out / f"{stem}.gif", []
                for cap in l5.GIF_FRAME_CAPS:
                    step, keep = l5.gif_ticks(int(rec["frames"]), hold, cap)
                    gcap = r3.caption(m["variant"], speed * step, source=source)
                    frames = [f for _, f in l5._overlaid(raw, t, view, res, gcap, result, info, keep)]
                    if len(frames) != len(keep):
                        raise RuntimeError(f"{len(frames)} GIF frames, expected {len(keep)}")
                    frames += [frames[-1]] * hold
                    gi = l5.fit_gif(frames, gif, fps, float(pb["gif_max_mb"]))
                    tried.append({"frame_cap": cap, "step": step, "fits": gi is not None})
                    if gi is not None:
                        if step > 1:
                            imageio.imwrite(str(stem_dir / f"gif_{cam}_last.png"), frames[-1])
                        files["gif"] = gi | {"file": gif.name, "mb": round(gif.stat().st_size / 1e6, 2),
                                             "frames": len(frames), "tick_step": step, "speed_x": speed * step,
                                             "caption": gcap}
                        break
                else:
                    raise RuntimeError(f"no GIF fits {pb['gif_max_mb']} MB at {fps} frames/s: {tried}")
            except Exception as err:             # noqa: BLE001  (recorded; the MP4 and the other clips stay)
                files["gif_error"] = repr(err)
                say(f"{stem}.gif FAILED: {err!r}")
        done[rec["stem"]] = entry
    return done


# ============================================================================================ main
def parse(argv):
    ap = argparse.ArgumentParser(prog="ste_ls1_clips.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--equivalence", type=Path, action="append", required=True,
                    help="a finished equivalence read folder (LS1.2; read only); once per side")
    ap.add_argument("--out", type=Path, required=True, help="the clips' folder (not inside a read folder)")
    ap.add_argument("--skill-net", type=Path, action="append", default=[],
                    help="a read's network file, when run.json's skill_net_file is not inside svg_training/ (matched "
                         "by the read's net_sha256)")
    ap.add_argument("--settings", default=None, help="the video settings (default configs/ste_video.toml)")
    ap.add_argument("--picks-per-side", type=int, default=DEFAULT_PICKS_PER_SIDE,
                    help=f"picks per side (default {DEFAULT_PICKS_PER_SIDE}, at least {MIN_PICKS_PER_SIDE}; RULE)")
    ap.add_argument("--plan-only", action="store_true", help="the checks, the picks and the ask only; writes nothing")
    return ap.parse_args(argv)


def write_report(out: Path, report: dict) -> None:
    atomic.write_text(out / CLIPS_JSON, json.dumps(report, indent=1))


def _say_plan(p: dict, count: int, asks: dict, cap: float) -> None:
    for x in p["picks"]:
        say(f"  {x['side']} {x['pick']}: cell {x['cell']} ({x['kind']}, {'+'.join(x['codes'])} v {x['opponent']}) "
            f"game {x['game']} class {x['class']}; copy {x['arms'][COPY]['batch']}[{x['arms'][COPY]['global_index']}], "
            f"scripts {x['arms'][SCRIPTS]['batch']}[{x['arms'][SCRIPTS]['global_index']}]")
    e = p["estimate"]
    say(f"batch replays: {e['batch_replays']} (CPU, inside this job), CPU estimate {e['replay_cpu_s']:.1f} s "
        f"(the reads' own layout.json seconds of those batches)")
    say(f"to render: {e['trajectories']} trajectories, {e['ticks_to_render']} ticks x {CAMERAS} cameras; expected "
        f"{e['expected_s']:.0f} s; ask --gpu-h {e['ask_gpu_h']:.2f} at {count} picks per side (cap {cap:g})")
    say("ask by picks per side: " + ", ".join(f"{k}: {v:.2f}" for k, v in sorted(asks.items())))


def main(argv=None) -> int:
    a = parse(argv)
    from svg_training.viz.starling_look import SETTINGS_FILE

    settings = a.settings or str(SETTINGS_FILE)
    if a.picks_per_side < MIN_PICKS_PER_SIDE:
        say(f"refused: --picks-per-side {a.picks_per_side} is below MIN_PICKS_PER_SIDE = {MIN_PICKS_PER_SIDE}")
        return EXIT_REFUSED
    out = a.out.resolve()
    folders = [f.resolve() for f in a.equivalence]
    for f in folders:
        if out == f or f in out.parents or out in f.parents:
            say(f"refused: --out {eq.rel(out)} is a read folder, inside one, or holds one ({eq.rel(f)})")
            return EXIT_REFUSED
    try:
        reads = [load_read(f, a.skill_net) for f in folders]
        sides = [r.side for r in reads]
        if len(set(sides)) != len(sides):
            raise Refused(f"two reads of one side ({sides}): one read per side")
        cap = task_cap_gpu_h()
        asks = {}

        def ask_of(k: int) -> dict:
            est = plan(reads, k)["estimate"]
            asks[k] = est["ask_gpu_h"]
            return est
        count, _, fits = fit_to_cap(a.picks_per_side, cap, ask_of)
        p = plan(reads, count)
    except Refused as err:
        say(f"refused: {err}")
        return EXIT_REFUSED
    for r in reads:
        say(f"{r.name}: {r.side} team, verdict {r.results.get('verdict')}, of_record {r.results.get('of_record')}, "
            f"{r.ctx.n} games per cell, network {r.ctx.net_sha[:12]}")
    _say_plan(p, count, asks, cap)
    if count < a.picks_per_side:
        say(f"the ask at {a.picks_per_side} picks per side is above the LS1.6 cap {cap:g}: cut to {count} (RULE)")
    if not fits:
        say(f"refused: the ask {p['estimate']['ask_gpu_h']:.2f} GPU-h is above the LS1.6 cap {cap:g} even at "
            f"MIN_PICKS_PER_SIDE = {MIN_PICKS_PER_SIDE}: nothing is launched; the lead decides the cap (R39, OQ-4)")
        return EXIT_REFUSED
    if a.plan_only:
        return EXIT_DONE
    if (out / CLIPS_JSON).is_file() and json.loads((out / CLIPS_JSON).read_text()).get("complete") is True:
        say(f"refused: {eq.rel(out / CLIPS_JSON)} is complete already: new clips need a new folder")
        return EXIT_REFUSED
    out.mkdir(parents=True, exist_ok=True)
    (out / CLIPS_JSON).unlink(missing_ok=True)
    for stale in list((out / TRAJ_DIR).glob("*")) if (out / TRAJ_DIR).is_dir() else []:
        stale.unlink()                           # never leave an earlier launch's game to be drawn
    commit = l5.git_commit()
    report = {"what": "STE LS1.6: 3-D Isaac Lab clips of the copy (the skill network) beside the scripts, from the "
                      "LS1.2 equivalence read (scripts/ste_ls1_clips.py); observed in the training simulator, not a "
                      "flight",
              "reads": [{"folder": r.name, "side": r.side, "verdict": r.results.get("verdict"),
                         "of_record": r.results.get("of_record"), "gates_sha256": r.ctx.g.sha256,
                         "net_sha256": r.ctx.net_sha, "skill_net_file": eq.rel(r.net_file), "games_per_cell": r.ctx.n,
                         "device": r.ctx.device} for r in reads],
              "rule": RULE, "picks_requested": a.picks_per_side, "picks_per_side": {r.side: count for r in reads},
              "cap_gpu_h": cap, "asks_by_picks_per_side": asks, "estimate": p["estimate"], "commit": commit,
              "picks": p["picks"], "replays": p["replays"], "complete": False}
    started = time.time()
    try:
        code = capture(reads, p, out, commit)
    except Refused as err:
        say(f"refused: {err}")
        report["refused"] = str(err)
        write_report(out, report)
        return EXIT_REFUSED
    report.update({"picks": p["picks"], "replays": p["replays"], "capture_s": round(time.time() - started, 1)})
    drawn = [out / x["arms"][arm]["trajectory"] for x in p["picks"] if x["drawn"] for arm in ARMS]
    write_report(out, report)                    # complete: false until the clips are made
    if drawn:
        work = out / "work"
        t0 = time.time()
        rc = l5.render_stage(out, work, drawn, settings)
        report["render"] = {"exit": rc, "seconds": round(time.time() - t0, 1)}
        if rc != 0:
            say(f"render failed (exit {rc}); nothing encoded")
            write_report(out, report)
            return EXIT_GPU_BUSY if rc == EXIT_GPU_BUSY else EXIT_RENDER
        try:
            enc = encode_ls1(out, work, settings)
        except Exception as err:                 # noqa: BLE001  (recorded, exit 3)
            traceback.print_exc()
            report["encode_error"] = repr(err)
            write_report(out, report)
            return EXIT_RENDER
        failures, made = [], 0
        for x in p["picks"]:
            for arm, arm_rec in x["arms"].items():
                if arm_rec.get("stem") not in enc:
                    continue
                arm_rec.update(enc[arm_rec["stem"]])
                if "error" in arm_rec:
                    failures.append(f"{arm_rec['stem']}: {arm_rec['error']}")
                for cam, f in arm_rec.get("files", {}).items():
                    made += ("mp4" in f) + ("gif" in f)
                    failures += [f"{arm_rec['stem']} {cam} {kind}: {f[kind]}" for kind in ("mp4_error", "gif_error")
                                 if kind in f]
        report["clip_failures"], report["clips_made"] = failures, made
        if made == 0:
            code = EXIT_RENDER
            say("no clip at all was encoded")
        render_meta = json.loads((work / "render_meta.json").read_text())
        report["render"].update({k: render_meta.get(k) for k in ("isaac", "starling_usd", "starling_usd_sha256",
                                                                   "settings_file", "settings_sha256", "working_tree",
                                                                   "resolution")})
    else:
        report["render"] = {"exit": None, "note": "no pick has both arms equal to the read: nothing drawn"}
    report["games_drawn"] = {r.side: sum(1 for x in p["picks"] if x["side"] == r.side and x["drawn"]) for r in reads}
    report["picks"] = p["picks"]
    report["wall_s"] = round(time.time() - started, 1)
    report.pop("complete")
    report["complete"] = True                    # written last (the last key of the file)
    write_report(out, report)
    say(f"{CLIPS_JSON} written ({sum(report['games_drawn'].values())} of {len(p['picks'])} games drawn, both arms each; "
        f"{report.get('clips_made', 0)} clips, {len(report.get('clip_failures', []))} failed); exit {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
