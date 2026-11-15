#!/usr/bin/env python
"""Faster safety filter (S2 Task 7): how accurate and how fast each candidate setting of the filter is.

  filter_speed.py --gates configs/s2.toml --name <YYYY-MM-DD>_s2_filter_speed [--phase accuracy|speed|both]

A candidate is one (iterations, check_every) pair from ``[filter_speed]`` in the gates file: ``iterations`` is the
sweep budget, ``check_every`` the early stop of ``core/safety_filter.py`` (0 = the fixed loop of run T2).

Accuracy (phase 7a, CPU, float32): T2's scenes (``filter_parity.make_scenes`` with ``scenes`` and ``seed`` of
``[filter_speed_gates]``), CMU's filter once, then the port at every candidate; per candidate the five accuracy
gates: T2's four (``filter_parity.evaluate`` and ``cross_team_check``) and ``max_abs_dv_first_phase_mps`` (the
largest velocity difference on the scenes CMU solved without its Gauss-Seidel phase, decision D6).
``max_abs_dv_mps`` is compared at its written precision, 4 decimals (owner's ruling, 16 November 2026): the
measured value is rounded to 4 decimals first; every other gate compares as written (``gate_passes``).

Speed (phase 7b, GPU): the S2 game (``core/game.SvgGame``) with the Starling layer on, ``speed_case`` of
``[filter_speed]`` (5 Guard v 3 Strike, 4,096 games, 2 repeats), committed neutral values (no local file), random
actions in [-1, 1] drawn on the GPU inside the timed loop from a seeded generator; every candidate, plus one
baseline with the filter replaced by a pass-through (to give the share of the step spent in the filter). Timing:
``bench/timing.run_case`` with S0's warm-up (``configs/s0_benchmark.toml`` ``[timing]``, at least 2 s). Host syncs
per step are counted afterwards on a fresh game with ``torch.cuda.set_sync_debug_mode("warn")``.

Selection rule (``select_candidate``, fixed in the S2 plan): the fastest candidate whose ``iterations`` passes all
five accuracy gates and whose speed is at least ``game_steps_per_s_min`` -> PASS; otherwise FAIL.

Full game (``--phase fullgame``, INFO, run after the speed phase into the same folder, using its ``gates.toml``):
every early-stop candidate timed over one whole game from reset, with its host syncs; not used by the selection.

Writes into ``runs/<name>/``: ``gates.toml`` (copied first), ``accuracy.json/.md``, ``speed.json/.md``,
``selection.json``. Refuses to overwrite an output it would write. Exit 0 when the outputs were written (whatever
the gates say), 1 on refusal.
"""
import argparse
import contextlib
import hashlib
import json
import platform
import shutil
import sys
import time
import tomllib
import warnings
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import filter_parity as fp  # noqa: E402  (also puts source/ on the path)
from svg_training.bench.timing import gpu_name, run_case  # noqa: E402
from svg_training.core.game import SvgGame  # noqa: E402
from svg_training.core.game_config import CONFIGS, load_game_cfg  # noqa: E402
from svg_training.core.safety_filter import FilterResult  # noqa: E402
from svg_training.core.starling_layer import resolve_params  # noqa: E402
from svg_training.models import fitted  # noqa: E402

SIMULATOR = "Simulator: training simulator, tier 1 (safety-filter port vs CMU cbf_filter.py on T2's scenes, CPU)"
SPEED_SIMULATOR = ("Simulator: training simulator, tier 1 (S2 game with the Starling layer: exploratory drone "
                   "model, safety filter on every pair; GPU)")
GATE_ORDER = ["max_abs_dv_mps", "constraint_residual_max", "emergency_agreement_min", "cross_team_corrections",
              "max_abs_dv_first_phase_mps"]


# Owner's ruling, 16 November 2026 ("4 decimals. yes."): this gate's limit (T2's 1.6666038 written as 1.6666) is
# compared at its written precision, so the measured value is rounded to that many decimals first.
ROUNDED_DECIMALS = {"max_abs_dv_mps": 4}


def gate_passes(name: str, measured: float, limit: float) -> bool:
    """One accuracy gate: ``emergency_agreement_min`` is a lower limit, the others upper limits;
    ``max_abs_dv_mps`` is compared after rounding the measured value to 4 decimals (ROUNDED_DECIMALS)."""
    if name in ROUNDED_DECIMALS:
        measured = round(float(measured), ROUNDED_DECIMALS[name])
    return measured >= limit if name == "emergency_agreement_min" else measured <= limit


def accuracy_verdicts(gates: dict, ev: dict, cross: dict) -> list:
    """The five accuracy gates of one candidate: rows (name, measured, limit, passed, operator), in GATE_ORDER.

    gates: ``[filter_speed_gates]``; ev: ``filter_parity.evaluate``; cross: ``filter_parity.cross_team_check``.
    ``measured`` is the raw value; ``passed`` follows ``gate_passes``.
    """
    rows = [(n, m, lim, gate_passes(n, m, lim), op) for n, m, lim, _, op in fp.verdicts(gates, ev, cross)]
    first = float(ev["max_dv_subset_no_gs"])
    rows.append(("max_abs_dv_first_phase_mps", first, gates["max_abs_dv_first_phase_mps"],
                 gate_passes("max_abs_dv_first_phase_mps", first, gates["max_abs_dv_first_phase_mps"]), "<="))
    return rows


def _row_accurate(r: dict) -> bool:
    """A row with raw ``measured`` values and ``limits`` is judged here by ``gate_passes`` (so a table written
    before the owner's ruling is read under it); a row with only ``all_pass`` keeps it."""
    if "measured" in r and "limits" in r:
        return all(gate_passes(n, r["measured"][n], r["limits"][n]) for n in GATE_ORDER)
    return bool(r["all_pass"])


def select_candidate(accuracy: list, speed: list, min_game_steps_per_s: float) -> dict:
    """The S2 selection rule.

    accuracy: rows with ``iterations``, ``check_every`` and either raw ``measured`` + ``limits`` (judged by
    ``gate_passes``) or ``all_pass``; speed: rows with ``iterations``, ``check_every``, ``game_steps_per_s`` (None
    for a failed point: never chosen). An ``iterations`` count is accurate when every accuracy row measured with it
    passes all five gates. Returns ``verdict`` ("PASS" or "FAIL"), ``chosen`` (the fastest accurate candidate at or
    above the speed target, else None), ``fastest_accurate`` and ``fastest`` as (iterations, check_every) or None,
    and ``accurate_iterations`` (sorted list).
    """
    rows_by_it: dict = {}
    for r in accuracy:
        rows_by_it.setdefault(int(r["iterations"]), []).append(_row_accurate(r))
    accurate_it = {it for it, ok in rows_by_it.items() if all(ok)}
    measured = [r for r in speed if r.get("game_steps_per_s") is not None]
    ranked = sorted(measured, key=lambda r: -float(r["game_steps_per_s"]))
    key = lambda r: (int(r["iterations"]), int(r["check_every"]))  # noqa: E731
    accurate = [r for r in ranked if int(r["iterations"]) in accurate_it]
    chosen = next((key(r) for r in accurate if float(r["game_steps_per_s"]) >= min_game_steps_per_s), None)
    return {"verdict": "PASS" if chosen else "FAIL", "chosen": chosen,
            "fastest_accurate": key(accurate[0]) if accurate else None,
            "fastest": key(ranked[0]) if ranked else None, "accurate_iterations": sorted(accurate_it)}


def _max_dv(a: list, b: list) -> float:
    return float(max(np.max(np.abs(x - y)) for x, y in zip(a, b)))


def run_accuracy(gates_all: dict) -> dict:
    """Measure every candidate on T2's scenes. Returns {"rows": [...], "context": {...}}."""
    cand, gates = gates_all["filter_speed"], gates_all["filter_speed_gates"]
    if cand.get("accuracy_device", "cpu") != "cpu":
        raise ValueError("the accuracy phase runs on the CPU (T2's conditions)")
    dtype = torch.float32
    scenes = fp.make_scenes(int(gates["scenes"]), int(gates["seed"]))
    ref = fp.run_original(scenes)
    rows = []
    for it in [int(x) for x in cand["iterations"]]:
        fixed = None
        for k in [int(x) for x in cand["check_every"]]:
            port = fp.run_port(scenes, it, dtype, check_every=k)
            ev = fp.evaluate(scenes, ref, port)
            t0 = time.perf_counter()
            cross = fp.cross_team_check(scenes, port, it, dtype, check_every=k)
            cross_s = time.perf_counter() - t0
            if k == 0:
                fixed = port
            if fixed is None:  # check_every 0 not among the candidates: compare with the fixed loop anyway
                fixed = fp.run_port(scenes, it, dtype, check_every=0)
            verdict = accuracy_verdicts(gates, ev, cross)
            rows.append({
                "iterations": it, "check_every": k,
                "measured": {n: (float(m) if isinstance(m, float) else int(m)) for n, m, *_ in verdict},
                "limits": {n: lim for n, _, lim, _, _ in verdict},
                "passed": {n: bool(ok) for n, _, _, ok, _ in verdict},
                "all_pass": all(ok for *_, ok, _ in verdict),
                "max_dv_vs_fixed_loop_mps": _max_dv(port["vel"], fixed["vel"]),
                "emergency_vs_fixed_loop_disagree": int((port["emergency"] != fixed["emergency"]).sum()),
                "port_emergencies": int(port["emergency"].sum()),
                "max_abs_dv_gauss_seidel_scenes_mps": float(ev["max_dv_subset_gs"]),
                "cross_team_pairs": int(cross["cross_team_pairs"]),
                "port_seconds_cpu": float(port["seconds"]), "cross_check_seconds_cpu": cross_s,
            })
            print(f"iterations {it:5d} check_every {k:3d}: " + ", ".join(
                f"{n} {m:.6g}" if isinstance(m, float) else f"{n} {m}" for n, m, *_ in verdict)
                + f" -> {'PASS' if rows[-1]['all_pass'] else 'FAIL'} ({port['seconds']:.2f} s)", flush=True)
    s_idx = ref["converged"] & ~ref["emergency"]
    context = {
        "scenes": len(scenes), "seed": int(gates["seed"]), "dtype": "float32", "device": "cpu",
        "threads": torch.get_num_threads(),
        "original_subset_s": int(s_idx.sum()), "original_emergencies": int(ref["emergency"].sum()),
        "original_gauss_seidel_scenes": int((ref["sweeps"] > 200).sum()),
        "original_seconds": float(ref["seconds"]),
        "machine": f"{fp._cpu()}; torch {torch.__version__}, numpy {np.__version__}, "
                   f"Python {platform.python_version()}",
    }
    return {"rows": rows, "context": context}


def _fmt(x) -> str:
    """8 significant digits: the T2 limits are T2's values rounded to 5 or 6, so fewer digits could print a
    measured value equal to its limit next to FAIL."""
    return f"{x:.8g}" if isinstance(x, float) else str(x)


def write_accuracy_table(path: Path, result: dict, gates_path: Path) -> None:
    rows, ctx = result["rows"], result["context"]
    ops = {"emergency_agreement_min": ">="}
    lim = rows[0]["limits"] if rows else {}
    lines = [
        SIMULATOR, "",
        f"# Safety filter candidates: accuracy on T2's {ctx['scenes']} scenes (seed {ctx['seed']})", "",
        f"Gates `{gates_path}` `[filter_speed_gates]`; port on the CPU, float32, {ctx['threads']} threads; "
        f"{ctx['machine']}. CMU's filter: converged without emergency in {ctx['original_subset_s']} scenes "
        f"(subset S), emergency in {ctx['original_emergencies']}, Gauss-Seidel phase in "
        f"{ctx['original_gauss_seidel_scenes']}.", "",
        "Limits: " + ", ".join(f"`{n}` {ops.get(n, '<=')} {_fmt(lim[n])}" for n in GATE_ORDER if n in lim) + ". "
        "`max_abs_dv_mps` is compared after rounding the measured value to 4 decimals (its written precision; "
        "owner's ruling, 16 November 2026); the table shows the raw value.", "",
        "| iterations | check_every | " + " | ".join(f"`{n}`" for n in GATE_ORDER)
        + " | all five | max abs dv vs fixed loop (m/s) | port s (CPU) |",
        "|---" * (len(GATE_ORDER) + 5) + "|",
    ]
    for r in rows:
        cells = [f"{_fmt(r['measured'][n])} {'PASS' if r['passed'][n] else 'FAIL'}" for n in GATE_ORDER]
        lines.append(f"| {r['iterations']} | {r['check_every']} | " + " | ".join(cells)
                     + f" | {'PASS' if r['all_pass'] else 'FAIL'} | {r['max_dv_vs_fixed_loop_mps']:.3g} | "
                     f"{r['port_seconds_cpu']:.2f} |")
    lines.append("")
    path.write_text("\n".join(lines))


# ------------------------------------------------------------------------------------------------ speed (7b)

def s0_timing() -> dict:
    """S0's timing settings (``configs/s0_benchmark.toml`` ``[timing]``) plus its 2 s minimum warm-up."""
    t = dict(tomllib.loads((CONFIGS / "s0_benchmark.toml").read_text())["timing"])
    t["min_warmup_s"] = 2.0  # bench/timing.measure's default, as S0 ran
    return t


@contextlib.contextmanager
def filter_passthrough():
    """Replace the safety filter inside the Starling layer by a pass-through (velocities unchanged, nothing
    corrected), for the baseline that gives the share of the step spent in the filter."""
    real = fitted.filter_velocities

    def passthrough(nominal_mps, pos_m, *args, **kwargs):
        none = torch.zeros(nominal_mps.shape[:2], dtype=torch.bool, device=nominal_mps.device)
        return FilterResult(velocities=nominal_mps, corrected=none,
                            residual=nominal_mps.new_zeros(nominal_mps.shape[0]), emergency=none.any(dim=-1))

    fitted.filter_velocities = passthrough
    try:
        yield
    finally:
        fitted.filter_velocities = real


def make_step(game: SvgGame, seed: int):
    """One timed call: random actions [N, M, 4] in [-1, 1] drawn on the game's device from a seeded generator,
    then one game step. Returns the floating outputs (the harness checks them for NaN) and the reset fraction."""
    dev = torch.device(game.device)
    gen = torch.Generator(device=dev)
    gen.manual_seed(seed)
    n, g, m = game.num_games, game.guards, game.M

    def step() -> dict:
        a = torch.rand(n, m, 4, generator=gen, device=dev) * 2.0 - 1.0
        out = game.step({"guard": a[:, :g], "strike": a[:, g:]})
        return {"obs_guard": out.obs["guard"], "obs_strike": out.obs["strike"], "reward_guard": out.reward["guard"],
                "reward_strike": out.reward["strike"], "reset_fraction": out.done.float().mean()}

    return step


def count_syncs_per_step(game: SvgGame, seed: int, steps: int) -> float | None:
    """Host syncs per game step on CUDA (``set_sync_debug_mode("warn")``, a prototype PyTorch feature that may miss
    some syncs), over ``steps`` steps after 3 untimed ones. None on the CPU."""
    if not str(game.device).startswith("cuda"):
        return None
    step = make_step(game, seed)
    for _ in range(3):
        step()
    torch.cuda.synchronize()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        torch.cuda.set_sync_debug_mode("warn")
        try:
            for _ in range(steps):
                step()
        finally:
            torch.cuda.set_sync_debug_mode("default")
    return sum("synchroniz" in str(w.message) for w in caught) / steps


def _speed_point(cfg, case: dict, timing: dict, device: str, seed: int, sync_steps: int) -> dict:
    n, g, s = case["num_games"], case["guards"], case["strikes"]
    rows = run_case(lambda: SvgGame(cfg, n, g, s, device=device, seed=seed), lambda game: make_step(game, seed),
                    {"name": case["name"], "tier": 1, "guards": g, "strikes": s}, n, timing, device,
                    timing["min_warmup_s"])
    ok = [r for r in rows if r["status"] == "ok"]
    rates = [r["env_steps_per_s"] for r in ok]
    point = {"status": rows[0]["status"] if not ok else "ok", "error": rows[0].get("error"),
             "repeats_game_steps_per_s": rates,
             "game_steps_per_s": float(np.mean(rates)) if ok and len(ok) == len(rows) else None,
             "repeat_spread": (abs(rates[0] - rates[-1]) / float(np.mean(rates))) if len(rates) > 1 else 0.0,
             "nan_count": sum(r["nan_count"] for r in ok), "peak_mem_mb": max((r["peak_mem_mb"] for r in ok),
                                                                               default=None),
             "timed_steps": [r["timed_steps"] for r in ok], "timed_s": [r["timed_s"] for r in ok],
             "mean_reset_fraction": float(np.mean([r["mean_reset_fraction"] for r in ok])) if ok else None}
    point["drone_steps_per_s"] = None if point["game_steps_per_s"] is None else point["game_steps_per_s"] * (g + s)
    if ok and sync_steps > 0:
        game = SvgGame(cfg, n, g, s, device=device, seed=seed)
        point["syncs_per_step"] = count_syncs_per_step(game, seed, sync_steps)
        del game
    else:
        point["syncs_per_step"] = None
    if str(device).startswith("cuda"):
        torch.cuda.empty_cache()
    return point


def run_speed(gates_all: dict, device: str, game_config: Path, timing: dict, seed: int, sync_steps: int) -> dict:
    """Every candidate of ``[filter_speed]`` and the pass-through baseline on the S2 game with the Starling layer.
    Returns {"rows": [...], "baseline": {...}, "context": {...}}."""
    cand = gates_all["filter_speed"]
    sc = dict(cand["speed_case"])
    if sc.get("actions", "random") != "random":
        raise ValueError("speed_case.actions must be 'random'")
    timing = {**timing, "repeats": int(sc["repeats"])}
    base_cfg, prov = load_game_cfg(game_config, use_local=False)  # the committed neutral values, no local file
    case = {"guards": int(sc["guards"]), "strikes": int(sc["strikes"]), "num_games": int(sc["num_games"])}
    first_it = int(cand["iterations"][0])

    def cfg_of(it: int, k: int):
        return base_cfg.replace(**{"starling.enabled": True, "starling.filter_iterations": it,
                                   "starling.filter_check_every": k})

    with filter_passthrough():
        baseline = _speed_point(cfg_of(first_it, 0), {**case, "name": "filter_passthrough"}, timing, device, seed,
                                sync_steps)
    print(f"baseline (filter pass-through): {baseline['game_steps_per_s']} game-steps/s", flush=True)
    rows = []
    for it in [int(x) for x in cand["iterations"]]:
        for k in [int(x) for x in cand["check_every"]]:
            t0 = time.perf_counter()
            pt = _speed_point(cfg_of(it, k), {**case, "name": f"it{it}_k{k}"}, timing, device, seed, sync_steps)
            rate, base = pt["game_steps_per_s"], baseline["game_steps_per_s"]
            pt.update({"iterations": it, "check_every": k, "wall_s": time.perf_counter() - t0,
                       "filter_share": (1.0 - rate / base) if rate and base else None})
            rows.append(pt)
            print(f"iterations {it:5d} check_every {k:3d}: {rate} game-steps/s, syncs/step {pt['syncs_per_step']}, "
                  f"filter share {pt['filter_share']}, status {pt['status']} ({pt['wall_s']:.0f} s)", flush=True)
    params_path = resolve_params(base_cfg.starling.params)
    params = fitted.load_params(params_path)
    context = {
        "device": device, "gpu": gpu_name(device), "torch": torch.__version__,
        "game_config": prov.game_file, "game_config_sha256": prov.game_sha256, "local_file": prov.local_file,
        "starling_params": base_cfg.starling.params,
        "starling_params_sha256": hashlib.sha256(params_path.read_bytes()).hexdigest(),
        "filter": dict(params["filter"]), "case": case, "seed": seed, "timing": timing, "sync_steps": sync_steps,
        "preset": base_cfg.preset,
    }
    return {"rows": rows, "baseline": baseline, "context": context}


def _rate(x) -> str:
    return "-" if x is None else f"{x:,.0f}"


def write_speed_table(path: Path, result: dict, selection: dict | None, min_rate: float) -> None:
    ctx, base = result["context"], result["baseline"]
    acc_it = set(selection["accurate_iterations"]) if selection else set()
    lines = [
        SPEED_SIMULATOR, "",
        f"# Safety filter candidates: speed in the S2 game ({ctx['case']['guards']} Guard v {ctx['case']['strikes']} "
        f"Strike, {ctx['case']['num_games']:,} games, Starling layer on)", "",
        f"{ctx['gpu']}, torch {ctx['torch']}; game config `{ctx['game_config']}` (sha256 "
        f"{ctx['game_config_sha256'][:12]}), no local file; seed {ctx['seed']}; timing {ctx['timing']}. "
        f"Speed target {min_rate:,.0f} game-steps/s.", "",
        f"Baseline, filter replaced by a pass-through: {_rate(base['game_steps_per_s'])} game-steps/s "
        f"(repeats {', '.join(_rate(x) for x in base['repeats_game_steps_per_s'])}).", "",
        "| iterations | check_every | game-steps/s (mean of repeats) | repeats | repeat spread | share of step in filter "
        "| host syncs per step | accuracy (all five) | at or above target |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in result["rows"]:
        share = "-" if r["filter_share"] is None else f"{r['filter_share']:.1%}"
        sync = "-" if r["syncs_per_step"] is None else f"{r['syncs_per_step']:.2f}"
        acc = ("PASS" if r["iterations"] in acc_it else "FAIL") if selection else "-"
        hit = "-" if r["game_steps_per_s"] is None else ("yes" if r["game_steps_per_s"] >= min_rate else "no")
        lines.append(f"| {r['iterations']} | {r['check_every']} | {_rate(r['game_steps_per_s'])} | "
                     f"{', '.join(_rate(x) for x in r['repeats_game_steps_per_s'])} | {r['repeat_spread']:.3f} | "
                     f"{share} | {sync} | {acc} | {hit} |")
    if selection:
        lines += ["", f"Selection: **{selection['verdict']}**; chosen {selection['chosen']}; fastest accurate "
                  f"{selection['fastest_accurate']}; fastest {selection['fastest']}."]
    lines.append("")
    path.write_text("\n".join(lines))


def run_full_game(gates_all: dict, device: str, game_config: Path, seed: int, segment: int = 100,
                  count_syncs: bool = True) -> dict:
    """INFO, not used by the selection rule: every early-stop candidate (check_every > 0) timed over one whole game
    from reset (``game_ticks`` steps, all games starting together, random actions as in the speed phase), with the
    rate per ``segment`` steps, and the host syncs per step counted over a second whole game. The early stop's cost
    depends on how crowded the games are, so a short timing window at one point of the game need not stand for a
    whole game. The fixed loop (check_every 0) does the same work at every step and is not repeated here."""
    cand = gates_all["filter_speed"]
    sc = dict(cand["speed_case"])
    n, g, s = int(sc["num_games"]), int(sc["guards"]), int(sc["strikes"])
    base_cfg, prov = load_game_cfg(game_config, use_local=False)
    cuda = str(device).startswith("cuda")
    rows = []
    for it in [int(x) for x in cand["iterations"]]:
        for k in [int(x) for x in cand["check_every"] if int(x) > 0]:
            cfg = base_cfg.replace(**{"starling.enabled": True, "starling.filter_iterations": it,
                                      "starling.filter_check_every": k})
            ticks = cfg.game_ticks()
            warm = make_step(SvgGame(cfg, n, g, s, device=device, seed=seed), seed)
            for _ in range(5):                       # allocations and caches, on a throwaway game
                warm()
            del warm
            step = make_step(SvgGame(cfg, n, g, s, device=device, seed=seed), seed)
            seg_s = []
            if cuda:
                torch.cuda.synchronize()
            t0 = t_seg = time.perf_counter()
            for i in range(ticks):
                step()
                if (i + 1) % segment == 0 or i + 1 == ticks:
                    if cuda:
                        torch.cuda.synchronize()     # one per segment, outside the filter's own checks
                    now = time.perf_counter()
                    seg_s.append(now - t_seg)
                    t_seg = now
            total_s = time.perf_counter() - t0
            seg_steps = [min(segment, ticks - j * segment) for j in range(len(seg_s))]
            syncs = None
            if count_syncs and cuda:
                syncs = count_syncs_per_step(SvgGame(cfg, n, g, s, device=device, seed=seed), seed, ticks - 3)
            rows.append({"iterations": it, "check_every": k, "steps": ticks,
                         "game_steps_per_s": n * ticks / total_s, "seconds": total_s,
                         "segment_steps": segment,
                         "segment_game_steps_per_s": [n * m / x for m, x in zip(seg_steps, seg_s)],
                         "syncs_per_step": syncs})
            print(f"full game: iterations {it:5d} check_every {k:3d}: {rows[-1]['game_steps_per_s']:.0f} game-steps/s "
                  f"over {ticks} steps ({total_s:.0f} s); syncs/step {syncs}; per {segment} steps "
                  f"{[round(x) for x in rows[-1]['segment_game_steps_per_s']]}", flush=True)
            if cuda:
                torch.cuda.empty_cache()
    return {"rows": rows, "context": {"device": device, "gpu": gpu_name(device), "torch": torch.__version__,
                                      "game_config": prov.game_file, "game_config_sha256": prov.game_sha256,
                                      "local_file": prov.local_file, "case": {"guards": g, "strikes": s,
                                                                              "num_games": n}, "seed": seed}}


def write_full_game_table(path: Path, result: dict) -> None:
    ctx = result["context"]
    lines = [SPEED_SIMULATOR, "",
             f"# INFO: early-stop candidates over one whole game ({ctx['case']['guards']} Guard v "
             f"{ctx['case']['strikes']} Strike, {ctx['case']['num_games']:,} games from reset, random actions)", "",
             f"{ctx['gpu']}, torch {ctx['torch']}, seed {ctx['seed']}. Not used by the selection rule.", "",
             "| iterations | check_every | game-steps/s over the whole game | slowest / fastest 100-step stretch "
             "| host syncs per step (whole game) |", "|---|---|---|---|---|"]
    for r in result["rows"]:
        seg = r["segment_game_steps_per_s"]
        sync = "-" if r["syncs_per_step"] is None else f"{r['syncs_per_step']:.1f}"
        lines.append(f"| {r['iterations']} | {r['check_every']} | {_rate(r['game_steps_per_s'])} | "
                     f"{_rate(min(seg))} / {_rate(max(seg))} | {sync} |")
    lines.append("")
    path.write_text("\n".join(lines))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--gates", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--phase", default="both", choices=["accuracy", "speed", "both", "fullgame"],
                   help="fullgame: INFO timing of the early-stop candidates over one whole game (after the run)")
    p.add_argument("--runs-dir", default=str(ROOT / "runs"))
    p.add_argument("--device", default="cuda", help="speed phase only (the accuracy phase always runs on the CPU)")
    p.add_argument("--game-config", default=str(CONFIGS / "s2_game.toml"))
    p.add_argument("--seed", type=int, default=0, help="game and action seed of the speed phase")
    p.add_argument("--sync-steps", type=int, default=20, help="steps over which host syncs are counted (CUDA)")
    p.add_argument("--timing-override", default=None,
                   help="tests only: JSON merged into S0's timing, e.g. '{\"timed_steps\": 3}'")
    a = p.parse_args(argv)
    gates_path = Path(a.gates).resolve()
    gates_all = tomllib.loads(gates_path.read_text())
    out = Path(a.runs_dir) / a.name
    writes = {"accuracy": ["accuracy.json"], "speed": ["speed.json"], "both": ["accuracy.json", "speed.json"],
              "fullgame": ["fullgame.json"]}
    for f in writes[a.phase]:
        if (out / f).exists():
            print(f"refusing to overwrite {out / f}", file=sys.stderr)
            return 1
    if a.phase != "accuracy" and a.device.startswith("cuda") and not torch.cuda.is_available():
        print("the speed phase needs CUDA (or --device cpu for a test)", file=sys.stderr)
        return 1
    if a.phase == "fullgame":
        if not (out / "gates.toml").exists():
            print(f"fullgame is an addition to an existing run folder; {out / 'gates.toml'} is missing",
                  file=sys.stderr)
            return 1
        full = run_full_game(tomllib.loads((out / "gates.toml").read_text()), a.device, Path(a.game_config), a.seed,
                             count_syncs=a.sync_steps > 0)
        (out / "fullgame.json").write_text(json.dumps(full, indent=1))
        write_full_game_table(out / "fullgame.md", full)
        print(f"wrote {out / 'fullgame.json'} and {out / 'fullgame.md'}")
        return 0
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(gates_path, out / "gates.toml")
    gates = gates_all["filter_speed_gates"]
    accuracy = None
    if a.phase in ("accuracy", "both"):
        threads = torch.get_num_threads()
        torch.set_num_threads(min(8, threads))  # T2's setting: more threads were 25x slower on the laptop
        try:
            accuracy = run_accuracy(gates_all)
        finally:
            torch.set_num_threads(threads)
        accuracy["gates_file"] = str(gates_path)
        (out / "accuracy.json").write_text(json.dumps(accuracy, indent=1))
        write_accuracy_table(out / "accuracy.md", accuracy, gates_path)
        print(f"wrote {out / 'accuracy.json'} and {out / 'accuracy.md'}")
    elif (out / "accuracy.json").exists():
        accuracy = json.loads((out / "accuracy.json").read_text())
    if a.phase in ("speed", "both"):
        timing = s0_timing()
        if a.timing_override:
            timing.update(json.loads(a.timing_override))
        speed = run_speed(gates_all, a.device, Path(a.game_config), timing, a.seed, a.sync_steps)
        speed["gates_file"] = str(gates_path)
        selection = None
        if accuracy is not None:
            selection = select_candidate(accuracy["rows"], speed["rows"], gates["game_steps_per_s_min"])
            (out / "selection.json").write_text(json.dumps(selection, indent=1))
            print(f"selection: {selection}")
        (out / "speed.json").write_text(json.dumps(speed, indent=1))
        write_speed_table(out / "speed.md", speed, selection, gates["game_steps_per_s_min"])
        print(f"wrote {out / 'speed.json'} and {out / 'speed.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
