#!/usr/bin/env python
"""STE task L0.12d Cross-tag check (INFO): the players T46 trained at tag 1.6 m (base) scored in the 1.15 m game.

    ste_cross_tag_l012d.py --t46-runs-dir <folder holding T46's two run folders> --run-dir runs/<date>_ste_l012d_cross_tag
                           --cap-h <GPU-h> [--settings configs/ste_l012d/cross_tag.toml] [--no-videos]

Launch through ``scripts/ste_job.py launch --task L0.12 --gpu-h <H> ... -- <this command> --cap-h <H>`` (the same H: a
run folder whose job.json asks for other hours, or a GPU job on the CPU, is refused). Scoring only, no training; tier 1;
results are "observed in the training simulator". Spec: ste_learning/drafts/L0_12d_CROSS_TAG_SPEC.md.

What it does, in order (settings and every pin: ``configs/ste_l012d/cross_tag.toml``):
1. checks every pinned file by sha256 before anything plays: each T46 run's gates.toml, agent_final.pt (hashed before it
   is loaded) and eval_final.npz; the L0.12b gate file; both game files (base, tag 1.15 m); both reference files and
   their start sets (one start set, T44's). Any mismatch: exit 2, nothing played;
2. C1, C2: each T46 run's evaluation batch replayed whole (every cell, the base game, ``exploit.play_cells`` with the
   network rebuilt by ``exploit_train.team_from_modules`` as ``scripts/ste_vid1_capture.py`` does): equal to the run's
   eval_final.npz game for game (``viz/replay3d.check_against_record``: exact keys equal, closest approach within the
   L0.11 same_seed_closest_tol_m on CUDA, 0 on the CPU) and the trained cell's count the record's (913, 636);
3. X4's own base-game batch (a separate batch: C2's is replayed whole): X4 (guard_field, the 1.15 m g*, v T46 Strike at
   1.6 m; the T46 Strike team never trained against guard_field) and the script cell guard_field v s* at 1.6 m. C4: its
   script cell equal to T44's reference game for game (``exploit.replay_ok``'s exact rule on any device: outcome, end
   step, tags, Strike drones left; the reference stores no closest approach), guard_field v strike_straight holding 716;
4. one 1.15 m batch on the screen reference's starts: X1 (T46 Guard v s* at 1.15 m), X2 (g* at 1.15 m v T46 Strike), X3
   (the base g* v T46 Strike, INFO), and the script cells g* v s* and base g* v s* at 1.15 m. C3: every script cell equal
   to the screen reference game for game (the same exact rule) on the reference's starts, g* v s* holding 645;
5. only when C1-C4 all PASS: results.json / results.md (wins of the trained side with Wilson 95 % intervals, Guards left in
   holds, game length median, the unchosen-tag shares, and for X1, X2 and X4 the paired counts against the script cell of
   the same batch), and the 2-D clips (the L0.12 driver's ``make_videos``: CPU, own starts from the L0.12b clip seed, never
   the scored games), one win and one loss of X1 and of X2 where the recorded games hold both. The clips run last, only
   with cap left; an error there is caught and the clips are marked missing (results.json still complete).

Every batch's per-game record is kept in ``games/`` as soon as it is played (for diagnosis, also when its control
fails); no X number is summarised or reported unless every control passes. The run
contract (``ste/run_contract.py``): the same command resumes at the next batch not yet checked; SIGINT or SIGTERM stops
before the next tick (exit 4); the cap is effective seconds = --cap-h x 3600 (exit 3). Exit codes: 0 done; 2 refused; 3
cap; 4 stopped on request; 5 a non-finite action; 6 CONTROL_FAILED (a control is not PASS: no X number is reported;
terminal, the same command on the same folder ends with 6 again)."""
from __future__ import annotations

import argparse
import dataclasses
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

import ste_exploit_l012 as l012  # noqa: E402  (win counts, plumbing controls, the exit rule, clips, the simulator words)
import ste_sweep_l011 as l011  # noqa: E402  (code pinning, JSON writing)
from svg_training.core.rewards import RUNNING  # noqa: E402
from svg_training.ste import atomic, exploit, exploit_train, scoring, sweep  # noqa: E402
from svg_training.ste.run_contract import (EXIT_CONTROL_FAILED, EXIT_DONE, EXIT_FOR_STOP, EXIT_NONFINITE,  # noqa: E402
                                           EXIT_REFUSED, STOP_CAP, RunBusyError, RunGuard)
from svg_training.viz import replay3d as r3  # noqa: E402

SETTINGS_FILE = ROOT / "configs" / "ste_l012d" / "cross_tag.toml"
SETTINGS_COPY, PINNED_SHA = "cross_tag.toml", "settings.sha256"
CONTROLS_FILE, RESULTS, GAMES = "controls.json", "results.json", "games"
HOUR_S = 3600.0
PASS, FAIL = l012.PASS, l012.FAIL
T46_GUARD, T46_STRIKE = "t46_base_guard", "t46_base_strike"      # the trained players' names in the batch's cells
SIDES = ("guard", "strike")
BATCH = {"guard": "c1_base_guard", "strike": "c2_base_strike"}
CONTROL = {"guard": "C1", "strike": "C2"}
X_BATCH, X4_BATCH = "x_tag_1p15", "c4_base_field"
CONTROLS = ("C1", "C2", "C3", "C4")
TOL_SOURCE = "configs/ste_l011/gates.toml"   # the L0.11 gate file: same_seed_closest_tol_m (sweep.GATES_FILE)
EXACT_RULE = scoring.EXACT_RULE   # exploit.replay_ok's game-for-game branch, applied on any device (C3)
SIMULATOR = l012.SIMULATOR
OBSERVED = "observed in the training simulator"
READING = ("1.6 m strategy at 1.15 m: {k:,} of {n:,} ({lo:.3f}–{hi:.3f}) against the 1.15 m-trained team's {m} and the "
           "script's {s}")
LIMITS = "one seed per side, one opponent, one start set; " + OBSERVED
_KEYS = {
    "t46": {"variant", "guard_run", "strike_run", "gates_sha256", "guard_agent_sha256", "strike_agent_sha256",
            "guard_eval_sha256", "strike_eval_sha256", "reference_sha256", "game_sha256", "guard_holds",
            "strike_reaches", "x4_script_holds"},
    "screen": {"gates", "gates_sha256", "variant", "reference_sha256", "game_sha256", "screen_holds"},
    "compare": {"trained_guard_holds", "trained_strike_reaches", "trained_games", "trained_source"},
    "clips": {"games", "keep"},
}


def say(text: str) -> None:
    print(f"[l012d] {text}", flush=True)


def refuse(text: str) -> int:
    print(f"refused: {text}", file=sys.stderr, flush=True)
    return EXIT_REFUSED


def parse(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--t46-runs-dir", type=Path, required=True, help="the folder holding T46's run folders (read only)")
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--cap-h", type=float, required=True, help="cap in effective hours (= the launcher's --gpu-h)")
    ap.add_argument("--settings", type=Path, default=SETTINGS_FILE)
    ap.add_argument("--no-videos", action="store_true", help="skip the clips (tests only)")
    ap.add_argument("--allow-code-change", action="store_true",
                    help="resume although the code differs from the first launch's (recorded in code.json)")
    return ap.parse_args(argv)


def load_settings(path: Path) -> dict:
    """The settings file, every section with exactly its keys (ValueError names an unknown or missing one)."""
    data = tomllib.loads(Path(path).read_text())
    unknown = sorted(set(data) - set(_KEYS))
    if unknown:
        raise ValueError(f"unknown section(s) in {Path(path).name}: {unknown}")
    for name, keys in _KEYS.items():
        exploit._exact(data.get(name), keys, name)
    return data


# ================================================================================================ cells
def x_cells(screen: exploit.ExploitGates, screen_variant: str, t46: exploit.ExploitGates, t46_variant: str) -> list:
    """The 1.15 m batch (Guard, Strike): X1, X2, X3, then the script cells g* v s* (1.15 m) and the base g* v s*."""
    g15, s15 = screen.variants[screen_variant]["g_star"], screen.variants[screen_variant]["s_star"]
    g_base = t46.variants[t46_variant]["g_star"]
    cells = [(T46_GUARD, s15), (g15, T46_STRIKE), (g_base, T46_STRIKE), (g15, s15), (g_base, s15)]
    return list(dict.fromkeys(cells))


def is_script_cell(cell: tuple) -> bool:
    return T46_GUARD not in cell and T46_STRIKE not in cell


def x4_cells(screen: exploit.ExploitGates, screen_variant: str, t46: exploit.ExploitGates, t46_variant: str) -> list:
    """X4's own base-game batch (Guard, Strike): guard_field (the 1.15 m g*) v T46 Strike, then guard_field v the base s*."""
    g15, s46 = screen.variants[screen_variant]["g_star"], t46.variants[t46_variant]["s_star"]
    return [(g15, T46_STRIKE), (g15, s46)]


def x_roles(screen: exploit.ExploitGates, screen_variant: str, t46: exploit.ExploitGates, t46_variant: str) -> dict:
    """X1-X4 by cell: {name: {batch, game, cell, side, script}}; ``script`` is the script cell of the same batch it is
    paired with (None for X3)."""
    g15, s15 = screen.variants[screen_variant]["g_star"], screen.variants[screen_variant]["s_star"]
    g_base, s_base = t46.variants[t46_variant]["g_star"], t46.variants[t46_variant]["s_star"]
    return {"X1": {"batch": X_BATCH, "game": screen_variant, "cell": (T46_GUARD, s15), "side": "guard", "script": (g15, s15)},
            "X2": {"batch": X_BATCH, "game": screen_variant, "cell": (g15, T46_STRIKE), "side": "strike",
                   "script": (g15, s15)},
            "X3": {"batch": X_BATCH, "game": screen_variant, "cell": (g_base, T46_STRIKE), "side": "strike", "script": None},
            "X4": {"batch": X4_BATCH, "game": t46_variant, "cell": (g15, T46_STRIKE), "side": "strike",
                   "script": (g15, s_base)}}


def role_index(role: dict, cells_by_batch: dict) -> tuple[int, int | None]:
    """(the X cell's index, its script cell's index or None) in its batch, looked up by cell (never by position)."""
    cells = [tuple(c) for c in cells_by_batch[role["batch"]]]
    return cells.index(tuple(role["cell"])), (None if role["script"] is None else cells.index(tuple(role["script"])))


# ================================================================================================ the inputs
_sha_problem = scoring.sha_problem            # the shared scoring parts (ste/scoring.py, factored out for L1)


def _reference(gates: exploit.ExploitGates, pin: str, what: str) -> tuple[object, str | None]:
    path = ROOT / gates.reference["file"]
    for want, src in ((gates.reference["sha256"], "its gate file"), (pin, "the settings")):
        if not path.is_file() or exploit.sha256_file(path) != want:
            return None, f"{what} reference {path} is missing or not the one {src} pins ({want[:12]})"
    ref = exploit.load_reference(path)
    if ref.start_sha256 != gates.reference["start_sha256"]:
        return None, f"{what} reference starts sha256 {ref.start_sha256}, its gate file pins {gates.reference['start_sha256']}"
    if ref.meta.get("t44_gates_sha256") != gates.reference["t44_gates_sha256"]:
        return None, f"{what} reference was made under gate sha256 {ref.meta.get('t44_gates_sha256')}, its gate file pins " \
                     f"{gates.reference['t44_gates_sha256']}"
    return ref, None


def _game(gates: exploit.ExploitGates, variant: str, pin: str, what: str):
    problems = exploit.game_file_problems(gates)
    if problems:
        return None, f"{what}: game file(s) differ from the gate file: " + "; ".join(problems)
    game = gates.games[gates.variants[variant]["game"]]
    if game.sha256 != pin:
        return None, f"{what}: the gate file pins game {game.file} at {game.sha256}, the settings at {pin}"
    return exploit.variant_cfg(gates, variant), None


def check_inputs(a: argparse.Namespace, s: dict):
    """(the loaded inputs, None) or (None, the reason to refuse). Nothing is played here; every network file is hashed
    before it is loaded."""
    t = s["t46"]
    dirs = {side: a.t46_runs_dir / t[f"{side}_run"] for side in SIDES}
    for side, rd in dirs.items():
        for name, key in (("gates.toml", "gates_sha256"), ("agent_final.pt", f"{side}_agent_sha256"),
                          ("eval_final.npz", f"{side}_eval_sha256")):
            why = _sha_problem(rd / name, t[key], f"T46 {side} run's {name}")
            if why:
                return None, why
    try:
        t46 = exploit.load_gates(dirs["guard"] / "gates.toml")
        for rd in dirs.values():              # STE L3: a skills network is refused (not wired here yet)
            exploit.skills.require_velocity_learner(exploit.load_gates(rd / "gates.toml"), "scripts/ste_cross_tag_l012d.py")
        screen_file = ROOT / s["screen"]["gates"]
        why = _sha_problem(screen_file, s["screen"]["gates_sha256"], "the L0.12b gate file")
        if why:
            return None, why
        screen = exploit.load_gates(screen_file)
    except (OSError, ValueError) as err:
        return None, f"gate file: {err}"
    v46, v15 = t["variant"], s["screen"]["variant"]
    if v46 not in t46.variants or v15 not in screen.variants:
        return None, f"variant {v46!r} not in T46's gate file or {v15!r} not in the L0.12b gate file"
    cfg46, why = _game(t46, v46, t["game_sha256"], "T46")
    if why:
        return None, why
    cfg15, why = _game(screen, v15, s["screen"]["game_sha256"], "L0.12b")
    if why:
        return None, why
    ref46, why = _reference(t46, t["reference_sha256"], "T46's")
    if why:
        return None, why
    ref15, why = _reference(screen, s["screen"]["reference_sha256"], "the screen's")
    if why:
        return None, why
    if ref46.start_sha256 != ref15.start_sha256:
        return None, "T46's and the screen's references hold different start sets (the cells would not be paired)"
    for key in ("device", "size", "eval_games", "ticks_cap"):
        if t46.run[key] != screen.run[key]:
            return None, f"[run] {key}: T46's gate file {t46.run[key]!r}, the L0.12b gate file {screen.run[key]!r}"
    if list(t46.trainer["hidden"]) != list(screen.trainer["hidden"]):
        return None, "the networks' hidden sizes differ between the two gate files"
    device, n = str(t46.run["device"]), int(t46.run["eval_games"])
    if device.startswith("cuda") and not torch.cuda.is_available():
        return None, "the gate files play on cuda and PyTorch sees no GPU"
    if not (a.cap_h > 0 and a.cap_h < float("inf")):
        return None, f"--cap-h must be a finite number of hours above 0, got {a.cap_h!r}"
    job_file = a.run_dir / "job.json"
    if job_file.is_file():
        gpu_h = float(json.loads(job_file.read_text()).get("gpu_h", 0))
        if gpu_h > 0 and abs(gpu_h - a.cap_h) > 1e-9:
            return None, f"the launcher asked for {gpu_h} GPU-h, --cap-h is {a.cap_h}: keep the two equal"
        if (gpu_h > 0) != device.startswith("cuda"):
            return None, f"the launcher asked for {gpu_h} GPU-h and the gate files play on {device!r}"
    cells = {side: exploit.eval_cells(t46, v46, side) for side in SIDES}
    records = {}
    for side in SIDES:
        if exploit.EXPLOITER not in cells[side][0]:
            return None, f"cell 0 of T46's {side} evaluation batch is {cells[side][0]}, not the trained team"
        with np.load(dirs[side] / "eval_final.npz") as d:
            records[side] = {k: d[k] for k in r3.EXACT_KEYS + r3.CLOSE_KEYS if k in d.files}
        if len(records[side]["outcome"]) != len(cells[side]) * n:
            return None, f"T46's {side} eval_final.npz holds {len(records[side]['outcome'])} games, the batch " \
                         f"{len(cells[side])} cells x {n}"
    xc = x_cells(screen, v15, t46, v46)
    x4 = x4_cells(screen, v15, t46, v46)
    missing = [c for c in xc if is_script_cell(c) and (v15, *c) not in ref15.cells]
    missing += [c for c in x4 if is_script_cell(c) and (v46, *c) not in ref46.cells]
    if missing:
        return None, f"the screen reference has no cell {missing}"
    hidden = list(t46.trainer["hidden"])
    teams = {}
    for side in SIDES:
        modules = torch.load(dirs[side] / "agent_final.pt", map_location=device, weights_only=False)
        teams[side] = exploit_train.team_from_modules(side, modules, hidden, device)
        teams[side].name = T46_GUARD if side == "guard" else T46_STRIKE
    return SimpleNamespace(t46=t46, screen=screen, v46=v46, v15=v15, cfg46=cfg46, cfg15=cfg15, ref46=ref46, ref15=ref15,
                           device=device, n=n, ticks=int(t46.run["ticks_cap"]), hold=int(t46.trainer["decision_ticks"]),
                           size=t46.run["size"], cells=cells, records=records, x_cells=xc, x4_cells=x4, teams=teams,
                           dirs=dirs, roles=x_roles(screen, v15, t46, v46)), None


# ================================================================================================ controls
_status = scoring.control_status


def check_t46_batch(pg: dict, record: dict, ref, n: int, side: str, expected: int, tol: float) -> dict:
    """C1 / C2: the whole batch equal to T46's eval_final.npz (exact keys; closest approach within ``tol``) and the
    trained cell's wins equal ``expected``; with the batch's paired starts, one for one and non-finite checks
    (``scoring.check_replay_batch``)."""
    return scoring.check_replay_batch(pg, record, ref, n, side, expected, tol)


def check_reference_cells(pg: dict, cells: list, ref, variant: str, n: int, ticks: int, g_s: tuple, expected: int) -> dict:
    """C3 / C4: every script cell of the batch equal to the reference (the screen's; T44's) game for game
    (exploit.replay_ok's exact rule on any device) from the reference's own starts, and ``g_s`` holding ``expected``
    (``scoring.check_script_cells``)."""
    return scoring.check_script_cells(pg, cells, ref, variant, n, ticks, is_script_cell, g_s, expected)


# ================================================================================================ results
paired_wins = scoring.paired_wins
_rate = scoring.rate


def x_rows(ctx, pgs: dict, s: dict) -> dict:
    """X1-X4 (INFO): the trained side's wins with Wilson 95 % intervals, Guards left in holds, game length, unchosen
    tags; X1, X2, X4: the script cell of the same batch and the paired counts; X1, X2: the team trained at 1.15 m.
    ``pgs``: per-game arrays by batch name."""
    guards, _ = sweep.parse_size(ctx.size)
    cfgs = {X_BATCH: ctx.cfg15, X4_BATCH: ctx.cfg46}
    cells = {X_BATCH: ctx.x_cells, X4_BATCH: ctx.x4_cells}
    cmp_ = s["compare"]
    out = {}
    for name, role in ctx.roles.items():
        pg, side = pgs[role["batch"]], role["side"]
        i, j = role_index(role, cells)
        edge = exploit.edge_m(ctx.screen, cfgs[role["batch"]])
        cell_pg = exploit.slice_cell(pg, i, ctx.n)
        k, m = l012.win_count(cell_pg, side)
        comp = sweep.hold_composition({**cell_pg, "game_ticks": pg["game_ticks"]}, guards)
        row = {"cell": list(role["cell"]), "side": side, "game": role["game"], **_rate(k, m),
               "unfinished": int(np.sum(cell_pg["outcome"] == RUNNING)),
               "guards_left_mean_in_holds": comp["guards_left_mean_in_holds"], "length_median_s": comp["length_median_s"],
               "composition": comp, "tag_shares": sweep.tag_shares(cell_pg, edge), "counts": exploit.counts(cell_pg)}
        ci = f"({row['ci'][0]:.3f}–{row['ci'][1]:.3f})"
        if j is not None:
            s_pg = exploit.slice_cell(pg, j, ctx.n)
            row["script"] = {"cell": list(role["script"]), **_rate(*l012.win_count(s_pg, side))}
            row["paired"] = paired_wins(cell_pg["outcome"], s_pg["outcome"], side) \
                if not (cell_pg["outcome"] == RUNNING).any() and not (s_pg["outcome"] == RUNNING).any() else \
                {"trained_only": None, "script_only": None, "both": None, "neither": None, "sign_test_p": None,
                 "note": "unfinished games: no paired counts"}
        if name in ("X1", "X2"):
            trained = cmp_["trained_guard_holds"] if side == "guard" else cmp_["trained_strike_reaches"]
            row["trained_at_1p15"] = {**_rate(trained, cmp_["trained_games"]), "source": cmp_["trained_source"]}
            row["reading"] = READING.format(k=k, n=m, lo=row["ci"][0], hi=row["ci"][1], m=trained, s=row["script"]["k"])
        elif name == "X4":
            row["reading"] = (f"1.6 m strategy at 1.6 m against {role['cell'][0]}, an opponent the T46 Strike team never "
                              f"trained against: {k:,} of {m:,} {ci} against the script's {row['script']['k']} (INFO)")
        else:
            row["reading"] = (f"1.6 m strategy at 1.15 m: {k:,} of {m:,} {ci} against {role['cell'][0]}, the opponent "
                              f"it trained against (INFO)")
        out[name] = row
    return out


def clips_or_missing(guard, make) -> dict:
    """The clips phase: skipped (marked missing) when the cap is reached or a stop was asked; an error while drawing is
    caught and marked missing, so results.json is still complete."""
    if guard.stop_requested:
        return {"missing": "a stop was asked before the clips (SIGINT or SIGTERM)"}
    if guard.cap_reached():
        return {"missing": "the cap was reached before the clips"}
    try:
        return make()
    except Exception as err:                            # noqa: BLE001  (any drawing error: the scores stand)
        return {"missing": f"the clips failed: {type(err).__name__}: {err}"}


def make_clips(ctx, s: dict, run_dir: Path) -> dict:
    """X1 and X2 with the L0.12 driver's make_videos (2-D, height panel; CPU, own starts from the L0.12b clip seed):
    ``[clips] games`` recorded, one win and one loss first where the recorded games hold both."""
    gates = dataclasses.replace(ctx.screen, videos={**ctx.screen.videos, "games": int(s["clips"]["games"]),
                                                    "keep": int(s["clips"]["keep"])})
    out = {}
    for name, side in (("X1", "guard"), ("X2", "strike")):
        modules = torch.load(ctx.dirs[side] / "agent_final.pt", map_location="cpu", weights_only=False)
        shim = SimpleNamespace(modules=lambda m=modules: m)
        lines = l012.make_videos(gates, ctx.v15, side, ctx.cfg15, shim, run_dir / "clips" / name)
        kinds = {w for w in ("reach", "hold") if any(f"_{w}.gif" in x for x in lines)}
        note = None if kinds == {"reach", "hold"} else \
            f"the {s['clips']['games']} recorded games hold only {sorted(kinds) or 'no finished game'}"
        out[name] = {"files": [f"clips/{name}/{x}" for x in lines if x.startswith("videos/")], "note": note}
    return out


def _num(x, fmt: str = "{:.3f}") -> str:
    return "-" if x is None or (isinstance(x, float) and x != x) else fmt.format(x)


def _trained(x: dict) -> str:
    t = x.get("trained_at_1p15")
    return "-" if t is None else f"{t['k']}/{t['n']}"


def clip_starts(result: dict) -> str:
    """Which starts the clips use (the spec's Clips line; the record repeats it)."""
    return (f"Clips: the clip seed's own starts (clip_seed {result['clip_seed']}), CPU, not the "
            f"{result['eval_games']:,} scoring starts")


def write_md(run_dir: Path, controls: dict, result: dict | None) -> None:
    lines = [f"Simulator: {SIMULATOR}. {OBSERVED.capitalize()}; nothing here is a flight result.", "",
             "# L0.12d Cross-tag check: the 1.6 m-trained players (T46, base) in the 1.15 m game (INFO)", "",
             "## Controls (read these first; any control not PASS: no cross-tag number is reported)", "",
             "| Control | Status | Detail |", "|---|---|---|"]
    lines += [f"| {k} | **{v['status']}** | {v['detail']} |" for k, v in controls.items()]
    if result is not None:
        lines += ["", "## Result (INFO, no gate; " + LIMITS + ")", "",
                  "| Cell | Guard team | Strike team | Trained side's wins (Wilson 95 %) | Guards left in holds (mean) | "
                  "Length median (s) | Pushed together (share) | Filter active (share) |", "|---|---|---|---|---|---|---|---|"]
        for key, x in result["cells"].items():
            ts = x["tag_shares"]
            lines.append(f"| {key} ({x['game']}) | {x['cell'][0]} | {x['cell'][1]} | {x['k']}/{x['n']} "
                         f"({_num(x['ci'][0])}–{_num(x['ci'][1])})"
                         f" | {_num(x['guards_left_mean_in_holds'])} | {_num(x['length_median_s'])} | "
                         f"{ts.get('tags_pushed')} ({_num(ts.get('pushed_tag_share'))}) | "
                         f"{ts.get('tags_filtered')} ({_num(ts.get('filter_active_share'))}) |")
        lines += ["", "| Cell | Script cell (same starts) | Script's wins | Paired: trained only / script only / both / "
                  "neither | Trained at 1.15 m |", "|---|---|---|---|---|"]
        for key, x in result["cells"].items():
            if "script" in x:
                p = x["paired"]
                lines.append(f"| {key} | {' v '.join(x['script']['cell'])} | {x['script']['k']}/{x['script']['n']} | "
                             f"{p['trained_only']} / {p['script_only']} / {p['both']} / {p['neither']} | "
                             f"{_trained(x)} |")
        lines += ["", "## Reading", ""] + [f"- {k}: {x['reading']}." for k, x in result["cells"].items()]
        lines += ["", f"## Clips (2-D with the height panel): {clip_starts(result)}", ""]
        clips = result.get("clips", {})
        if "missing" in clips:
            lines.append(f"- no clips: {clips['missing']}")
        for key, c in clips.items():
            if key != "missing":
                lines += [f"- {key}: {f}" for f in c["files"]] + ([f"- {key}: {c['note']}"] if c.get("note") else [])
    atomic.write_text(run_dir / "results.md", "\n".join(lines) + "\n")


# ================================================================================================ the run
save_batch, load_batch = scoring.save_batch, scoring.load_batch


def run(ctx, a: argparse.Namespace, s: dict, guard: RunGuard) -> int:
    """C1, C2 (T46's batches), C4 (X4's base-game batch), C3 (the 1.15 m batch), in that order; each batch's npz as soon
    as it is played; results only when all four controls PASS."""
    run_dir = a.run_dir
    (run_dir / GAMES).mkdir(exist_ok=True)
    controls = json.loads((run_dir / CONTROLS_FILE).read_text()) if (run_dir / CONTROLS_FILE).is_file() else {}
    every, seen = int(ctx.t46.run["cap_check_every_ticks"]), [0]
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
        say(f"{key} {ctl['status']}: {ctl['detail']}")
        guard.save(len(controls), {"done": sorted(controls)})
        code = l012.ending({key: ctl})
        if code is not None:
            write_md(run_dir, controls, None)
            say(f"{'NON-FINITE' if code == EXIT_NONFINITE else 'CONTROL FAILED'}: no cross-tag number is reported "
                f"(exit {code}); the batch's per-game record is kept in {GAMES}/ for diagnosis")
        return code

    teams = {T46_GUARD: ctx.teams["guard"], T46_STRIKE: ctx.teams["strike"]}
    g15, s15 = ctx.screen.variants[ctx.v15]["g_star"], ctx.screen.variants[ctx.v15]["s_star"]
    s46 = ctx.t46.variants[ctx.v46]["s_star"]
    batches = [  # key, batch file, game, reference, cells, play keywords, check
        ("C1", BATCH["guard"], ctx.cfg46, ctx.ref46, ctx.cells["guard"], {"learner": ctx.teams["guard"]},
         lambda pg: check_t46_batch(pg, ctx.records["guard"], ctx.ref46, ctx.n, "guard", s["t46"]["guard_holds"], tol)),
        ("C2", BATCH["strike"], ctx.cfg46, ctx.ref46, ctx.cells["strike"], {"learner": ctx.teams["strike"]},
         lambda pg: check_t46_batch(pg, ctx.records["strike"], ctx.ref46, ctx.n, "strike", s["t46"]["strike_reaches"],
                                    tol)),
        ("C4", X4_BATCH, ctx.cfg46, ctx.ref46, ctx.x4_cells, {"players": teams},
         lambda pg: check_reference_cells(pg, ctx.x4_cells, ctx.ref46, ctx.v46, ctx.n, ctx.ticks, (g15, s46),
                                          s["t46"]["x4_script_holds"])),
        ("C3", X_BATCH, ctx.cfg15, ctx.ref15, ctx.x_cells, {"players": teams},
         lambda pg: check_reference_cells(pg, ctx.x_cells, ctx.ref15, ctx.v15, ctx.n, ctx.ticks, (g15, s15),
                                          s["screen"]["screen_holds"])),
    ]
    pgs = {}
    for key, name, cfg, ref, cells, players, check in batches:
        path = run_dir / GAMES / f"{name}.npz"
        if controls.get(key, {}).get("status") == PASS and path.is_file():
            if name in (X_BATCH, X4_BATCH):
                pgs[name] = load_batch(path)
            continue
        started = time.perf_counter()
        say(f"{key}: batch {name}, {len(cells)} cells x {ctx.n} on {ctx.device}: {cells}")
        try:
            pg = exploit.play_cells(cfg, ctx.size, ref, cells, ctx.n, ctx.device, int(ref.meta["seed"]), ctx.ticks,
                                    hold_ticks=ctx.hold, should_stop=should_stop, **players)
        except sweep.SweepStopped:
            return stopped()
        took = time.perf_counter() - started
        save_batch(path, pg)                                       # kept for diagnosis even when the control fails
        l011.write_json(path.with_suffix(".json"), {"cells": [list(c) for c in cells], "games_per_cell": ctx.n})
        code = settle(key, {**check(pg), "seconds": took})
        if code is not None:
            return code
        pgs[name] = pg
    if set(controls) != set(CONTROLS) or {v["status"] for v in controls.values()} != {PASS}:
        write_md(run_dir, controls, None)
        return EXIT_CONTROL_FAILED
    # ---- every control PASS: results, then the clips (last, with cap left); results.json LAST ----
    result = results_of(ctx, a, s, pgs, controls, guard, tol)
    result["clips"] = {} if a.no_videos else clips_or_missing(guard, lambda: make_clips(ctx, s, run_dir))
    result["complete"] = True
    l011.write_json(run_dir / RESULTS, result)
    write_md(run_dir, controls, result)
    guard.save(len(controls), {"done": sorted(controls), "phase": "done"})
    say("done: " + "; ".join(f"{k} {x['k']}/{x['n']}" for k, x in result["cells"].items()) + f"; {run_dir / 'results.md'}")
    return EXIT_DONE


def results_of(ctx, a, s: dict, pgs: dict, controls: dict, guard: RunGuard, tol: float) -> dict:
    game = lambda g, v: {"file": g.games[g.variants[v]["game"]].file, "sha256": g.games[g.variants[v]["game"]].sha256}  # noqa: E731
    machine = l012.machine()
    return {
        "what": "STE L0.12d Cross-tag check: the 1.6 m-trained players (T46, base) in the 1.15 m game; " + OBSERVED,
        "task": "L0.12d", "kind": "INFO", "simulator": SIMULATOR, "limits": LIMITS, "controls_pass": True,
        "controls": controls, "cells": x_rows(ctx, pgs, s),
        "x_cells": [list(c) for c in ctx.x_cells], "x4_cells": [list(c) for c in ctx.x4_cells],
        "networks": {side: {"run": s["t46"][f"{side}_run"], "agent_final_sha256": s["t46"][f"{side}_agent_sha256"],
                            "trained_on": ctx.v46, "decision_ticks": ctx.hold} for side in SIDES},
        "games": {"controls": game(ctx.t46, ctx.v46), "x": game(ctx.screen, ctx.v15), "x4": game(ctx.t46, ctx.v46)},
        "pins": {"t46": s["t46"], "screen": s["screen"]}, "compare": s["compare"],
        "references": {"t46": {"file": ctx.t46.reference["file"], "sha256": ctx.t46.reference["sha256"]},
                       "screen": {"file": ctx.screen.reference["file"], "sha256": ctx.screen.reference["sha256"]},
                       "start_sha256": ctx.ref15.start_sha256, "seed": int(ctx.ref15.meta["seed"])},
        "closest_tol": {"tol_m": tol, "rule": "0 on the CPU; same_seed_closest_tol_m on CUDA",
                        "source": TOL_SOURCE, "sha256": exploit.sha256_file(ROOT / TOL_SOURCE)},
        "clip_seed": int(ctx.screen.run["clip_seed"]),
        "parameter_set": l012.parameter_set(ctx.screen, ctx.v15), "device": ctx.device, "eval_games": ctx.n,
        "ticks_cap": ctx.ticks, "batch_seconds": {k: v.get("seconds") for k, v in controls.items()},
        "edge_m": exploit.edge_m(ctx.screen, ctx.cfg15), "effective_s": guard.effective_s(), "cap_h": a.cap_h,
        "machine": machine, "gpu": machine["gpu"], "code": json.loads((a.run_dir / l011.CODE_FILE).read_text()),
        "t46_runs_dir": str(a.t46_runs_dir), "settings_sha256": exploit.sha256_file(a.settings),
    }


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
        code = l012.ending(json.loads(controls_file.read_text()))
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
