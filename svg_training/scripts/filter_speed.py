#!/usr/bin/env python
"""Faster safety filter (S2 Task 7): how accurate and how fast each candidate setting of the filter is.

  filter_speed.py --gates configs/s2.toml --name <YYYY-MM-DD>_s2_filter_speed [--phase accuracy|speed|both]

A candidate is one (iterations, check_every) pair from ``[filter_speed]`` in the gates file: ``iterations`` is the
sweep budget, ``check_every`` the early stop of ``core/safety_filter.py`` (0 = the fixed loop of run T2).

Accuracy (phase 7a, CPU, float32): T2's scenes (``filter_parity.make_scenes`` with ``scenes`` and ``seed`` of
``[filter_speed_gates]``), CMU's filter once, then the port at every candidate; per candidate the five accuracy
gates: T2's four (``filter_parity.evaluate`` and ``cross_team_check``) and ``max_abs_dv_first_phase_mps`` (the
largest velocity difference on the scenes CMU solved without its Gauss-Seidel phase, decision D6). Writes
``runs/<name>/gates.toml`` (copied first), ``accuracy.json`` and ``accuracy.md``; refuses to overwrite.

Speed (phase 7b, GPU): not built yet; ``--phase speed`` or ``both`` exits 2 without writing anything.

Selection rule (``select_candidate``, fixed in the S2 plan): the fastest candidate whose ``iterations`` passes all
five accuracy gates and whose speed is at least ``game_steps_per_s_min`` -> PASS; otherwise FAIL.

Exit 0 when the outputs were written (whatever the gates say), 1 on refusal, 2 for a phase not built yet.
"""
import argparse
import json
import platform
import shutil
import sys
import time
import tomllib
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import filter_parity as fp  # noqa: E402

SIMULATOR = ("Simulator: training simulator, tier 1 (safety-filter port vs CMU cbf_filter.py on T2's scenes, "
             "CPU) - phase 7a accuracy table, not a run of record")
GATE_ORDER = ["max_abs_dv_mps", "constraint_residual_max", "emergency_agreement_min", "cross_team_corrections",
              "max_abs_dv_first_phase_mps"]


def accuracy_verdicts(gates: dict, ev: dict, cross: dict) -> list:
    """The five accuracy gates of one candidate: rows (name, measured, limit, passed, operator), in GATE_ORDER.

    gates: ``[filter_speed_gates]``; ev: ``filter_parity.evaluate``; cross: ``filter_parity.cross_team_check``.
    """
    rows = fp.verdicts(gates, ev, cross)  # T2's four, same names and operators
    first = float(ev["max_dv_subset_no_gs"])
    rows.append(("max_abs_dv_first_phase_mps", first, gates["max_abs_dv_first_phase_mps"],
                 first <= gates["max_abs_dv_first_phase_mps"], "<="))
    return rows


def select_candidate(accuracy: list, speed: list, min_game_steps_per_s: float) -> dict:
    """The S2 selection rule.

    accuracy: rows with ``iterations``, ``check_every``, ``all_pass``; speed: rows with ``iterations``,
    ``check_every``, ``game_steps_per_s``. An ``iterations`` count is accurate when every accuracy row measured
    with it passes all five gates. Returns ``verdict`` ("PASS" or "FAIL"), ``chosen`` (the fastest accurate
    candidate at or above the speed target, else None), ``fastest_accurate`` and ``fastest`` as
    (iterations, check_every) or None.
    """
    rows_by_it: dict = {}
    for r in accuracy:
        rows_by_it.setdefault(int(r["iterations"]), []).append(bool(r["all_pass"]))
    accurate_it = {it for it, ok in rows_by_it.items() if all(ok)}
    ranked = sorted(speed, key=lambda r: -float(r["game_steps_per_s"]))
    key = lambda r: (int(r["iterations"]), int(r["check_every"]))  # noqa: E731
    accurate = [r for r in ranked if int(r["iterations"]) in accurate_it]
    chosen = next((key(r) for r in accurate if float(r["game_steps_per_s"]) >= min_game_steps_per_s), None)
    return {"verdict": "PASS" if chosen else "FAIL", "chosen": chosen,
            "fastest_accurate": key(accurate[0]) if accurate else None,
            "fastest": key(ranked[0]) if ranked else None}


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
        "Limits: " + ", ".join(f"`{n}` {ops.get(n, '<=')} {_fmt(lim[n])}" for n in GATE_ORDER if n in lim) + ".", "",
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


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--gates", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--phase", default="both", choices=["accuracy", "speed", "both"])
    p.add_argument("--runs-dir", default=str(ROOT / "runs"))
    a = p.parse_args(argv)
    if a.phase != "accuracy":
        print("the speed phase (Task 7b) is not built yet; run --phase accuracy", file=sys.stderr)
        return 2
    gates_path = Path(a.gates).resolve()
    gates_all = tomllib.loads(gates_path.read_text())
    out = Path(a.runs_dir) / a.name
    if (out / "accuracy.json").exists():
        print(f"refusing to overwrite {out / 'accuracy.json'}", file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(gates_path, out / "gates.toml")
    threads = torch.get_num_threads()
    torch.set_num_threads(min(8, threads))  # T2's setting: more threads were 25x slower on the laptop
    try:
        result = run_accuracy(gates_all)
    finally:
        torch.set_num_threads(threads)
    result["gates_file"] = str(gates_path)
    (out / "accuracy.json").write_text(json.dumps(result, indent=1))
    write_accuracy_table(out / "accuracy.md", result, gates_path)
    print(f"wrote {out / 'accuracy.json'} and {out / 'accuracy.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
