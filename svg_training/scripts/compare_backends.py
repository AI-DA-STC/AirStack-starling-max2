#!/usr/bin/env python3
"""Compare paired scripted games on two motion backends (S2b Task 8): the physics drone against the tier 1 Starling
layer, cell by cell, against ``[compare_games_gates]`` of configs/s2b.toml.

    compare_backends.py --a runs/<n>_starling --b runs/<n>_physics_2v1,runs/<n>_physics_5v3 \\
        --gates configs/s2b.toml --name <n> [--runs-dir runs] [--init]

--a and --b are ``scripts/score.py --batch-per-pair`` output folders (comma lists: the physics side runs one size per
process); --a is the reference (tier 1, preset "starling"), --b the backend checked (preset "physics"). Each side must
hold exactly one preset. ``--init`` only writes ``runs/<name>/gates.toml`` (the gate table, before the score runs);
without it the comparison is written to ``runs/<name>/``: ``gates.toml`` (if not already there; if there, it must be
the same table), ``compare.json`` and ``compare.md``. A folder that already holds ``compare.json`` is never
overwritten.

A cell is one Guard x Strike x size x band: the same 1,000 game slots on both backends (paired: the same arena, zone and
starts per slot, checked here from per_game.npz, never assumed). Per cell:

  hold rate    share of finished first games the Guard team held, both backends, Wilson 95 % intervals; gap = b - a.
               Gate: |gap| <= max_cell_hold_gap.
  closest 3-D  the closest Guard-Strike approach per game in 3-D, in games WITHOUT a start miss (the same games on both
               sides: start misses are part of the paired draw) and finite values; minimum and 5th percentile (linear,
               as core/metrics.py). Gate (owner's decision A, 16 November 2026): b's minimum and b's 5th percentile
               each at most closest_cross_3d_gap_max_m below a's (one-sided: farther apart never fails).
  INFO         outcome agreement on paired slots (share of slots both finished with the same winner); mean end-step
               gap (b - a, steps of 0.05 s); breach share (3-D, under the keep-out) both sides.

Overall: upsets (games of b with an upset drone, D10) <= upsets_max; NaN <= nan_max, where NaN counts NaN values in
both sides' per-game closest-approach and filter arrays plus the physics drone's non-finite wrench values (score.py
meta). Verdict PASS when every cell passes both gates and the upset and NaN counts pass; anything missing or NaN
fails. Refused (ValueError; exit 2 from the CLI): side b not the physics preset, or missing its upset arrays or its
physics meta (non-finite wrench count) (the upset and NaN gates fail closed); a side that used a local partner file (only committed neutral values
are compared, so ``local_file`` is "none"), different seed, games per band, game config, or not --batch-per-pair, a
cell on one side only, or slots whose starts or arenas differ (not paired). The CLI also refuses folders that do not
hold the ``[compare_games]`` matchups, unless ``--no-config-check`` (tests only).

Exit codes: 0 written (PASS or FAIL is in the files), 2 refused or bad arguments, 1 crash.
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import pathlib
import sys
import tomllib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.metrics import wilson_interval  # noqa: E402

RUNNING, GUARD_WIN = 0, 2           # core/rewards.py outcome codes
BAND_ORDER = ("lab", "middle", "large")
PAIRING_FIELDS = ("start_pos_m", "arena_m", "start_miss")
NAN_FIELDS = ("closest_cross_m", "closest_cross_3d_m", "filter_corrected_rate")
TOL = 1e-9                          # float noise only; never a gate allowance


def load_side(dirs: list[str | pathlib.Path]) -> dict:
    """score.py output folders -> {"metas": [meta per folder], "per_game": merged per_game.npz arrays}."""
    metas, per_game = [], {}
    for d in dirs:
        d = pathlib.Path(d)
        metas.append(json.loads((d / "scores.json").read_text())["meta"])
        with np.load(d / "per_game.npz") as z:
            for k in z.files:
                if k in per_game:
                    raise ValueError(f"{k} appears in two folders of one side")
                per_game[k] = z[k]
    return {"metas": metas, "per_game": per_game}


def _cells(side: dict) -> dict[tuple[str, str, str, str], str]:
    """{(size, guard, strike, band): preset} from the per_game keys "preset|size|guard|strike|band|field"."""
    cells = {}
    for k in side["per_game"]:
        preset, size, gs, ss, band, field = k.split("|")
        if field == "outcome":
            cells[(size, gs, ss, band)] = preset
    return cells


def _one(metas: list[dict], key: str, label: str):
    vals = {json.dumps(m.get(key)) for m in metas}
    if len(vals) != 1:
        raise ValueError(f"{label}: the folders of one side differ in {key}")
    return metas[0].get(key)


def _check_inputs(a: dict, b: dict) -> tuple[str, str]:
    for name, side in (("a", a), ("b", b)):
        for m in side["metas"]:
            if m.get("local_file") is not None:
                raise ValueError(f"side {name} used a local partner file ({m.get('local_file')}): only committed "
                                 "neutral values (--no-local) are compared")
            if m.get("batch_per_pair") is not True:
                raise ValueError(f"side {name} was not scored with --batch-per-pair (batch_per_pair): games not paired")
    for key in ("seed", "games_per_band", "game_sha256"):
        va, vb = _one(a["metas"], key, "a"), _one(b["metas"], key, "b")
        if va != vb:
            raise ValueError(f"{key} differs: a {va}, b {vb}")
    presets = []
    for name, side in (("a", a), ("b", b)):
        ps = set(_cells(side).values())
        if len(ps) != 1:
            raise ValueError(f"side {name} must hold exactly one preset, holds {sorted(ps)}")
        presets.append(ps.pop())
    # the upset and NaN gates fail closed: side b must be the physics drone with its safety data (review, fix round 1)
    if presets[1] != "physics":
        raise ValueError(f"side b must be the physics preset (its upset and NaN gates need the physics drone's data); "
                         f"got {presets[1]!r}")
    for m in b["metas"]:
        ph = m.get("physics")
        if not isinstance(ph, dict):
            raise ValueError("side b: a score folder has no physics meta (non-finite wrench count): NaN gate not judged")
        nf = ph.get("nonfinite_count")
        if not isinstance(nf, int) or isinstance(nf, bool):
            raise ValueError(f"side b: physics meta nonfinite_count is {nf!r}, not a count: NaN gate not judged")
    return presets[0], presets[1]


def _closest(per_game: dict, key: str) -> tuple[float | None, float | None, int]:
    """(min, 5th percentile, games) of the 3-D closest approach: finished games without a start miss, finite values."""
    c = per_game[f"{key}|closest_cross_3d_m"].astype(np.float64)
    sel = (per_game[f"{key}|outcome"] != RUNNING) & ~per_game[f"{key}|start_miss"].astype(bool) & np.isfinite(c)
    c = c[sel]
    if c.size == 0:
        return None, None, 0
    return float(c.min()), float(np.quantile(c, 0.05)), int(c.size)


def _hold(per_game: dict, key: str) -> dict:
    o = per_game[f"{key}|outcome"]
    fin = o != RUNNING
    n, k = int(fin.sum()), int((o[fin] == GUARD_WIN).sum())
    lo, hi = wilson_interval(k, n)
    return {"games": n, "guard_wins": k, "hold_rate": k / n if n else None, "ci_low": lo if n else None,
            "ci_high": hi if n else None}


def _num(v) -> bool:
    return v is not None and isinstance(v, (int, float)) and math.isfinite(v)


def compare(a: dict, b: dict, gates: dict) -> dict:
    """a: the reference side (tier 1), b: the side checked (physics); each {"metas": [...], "per_game": {...}} as
    ``load_side`` returns. gates: the ``[compare_games_gates]`` table. Returns {"verdict", "cells": [...], "upsets",
    "nan", "local_file": "none", ...}; raises ValueError when the inputs cannot be compared (module docstring)."""
    pa, pb = _check_inputs(a, b)
    ca, cbb = _cells(a), _cells(b)
    if set(ca) != set(cbb):
        only = sorted(set(ca) ^ set(cbb))
        raise ValueError(f"cell(s) on one side only: {only[:4]}{' ...' if len(only) > 4 else ''}")
    hold_max = float(gates["max_cell_hold_gap"])
    gap_max = float(gates["closest_cross_3d_gap_max_m"])
    order = sorted(ca, key=lambda c: (c[0], c[1], c[2], BAND_ORDER.index(c[3]) if c[3] in BAND_ORDER else 9))
    cells = []
    nan = 0
    upsets = 0
    for cell in order:
        size, gs, ss, band = cell
        ka, kb = f"{pa}|{size}|{gs}|{ss}|{band}", f"{pb}|{size}|{gs}|{ss}|{band}"
        for f in PAIRING_FIELDS:
            xa, xb = a["per_game"].get(f"{ka}|{f}"), b["per_game"].get(f"{kb}|{f}")
            if xa is None or xb is None or xa.shape != xb.shape or not np.array_equal(xa, xb):
                raise ValueError(f"cell {cell}: {f} differs between the sides: games not paired")
        for side, k in ((a, ka), (b, kb)):
            for f in NAN_FIELDS:
                nan += int(np.isnan(side["per_game"][f"{k}|{f}"].astype(np.float64)).sum())
        ha, hb = _hold(a["per_game"], ka), _hold(b["per_game"], kb)
        gap = hb["hold_rate"] - ha["hold_rate"] if _num(ha["hold_rate"]) and _num(hb["hold_rate"]) else None
        hold_ok = gap is not None and abs(gap) <= hold_max + TOL
        amin, ap05, an = _closest(a["per_game"], ka)
        bmin, bp05, bn = _closest(b["per_game"], kb)
        min_gap = amin - bmin if _num(amin) and _num(bmin) else None        # > 0: physics came closer
        p05_gap = ap05 - bp05 if _num(ap05) and _num(bp05) else None
        closest_ok = (min_gap is not None and p05_gap is not None and min_gap <= gap_max + TOL
                      and p05_gap <= gap_max + TOL)
        oa, ob = a["per_game"][f"{ka}|outcome"], b["per_game"][f"{kb}|outcome"]
        both = (oa != RUNNING) & (ob != RUNNING)
        ea, eb = a["per_game"][f"{ka}|end_step"], b["per_game"][f"{kb}|end_step"]
        up = b["per_game"].get(f"{kb}|upset")
        if up is None or up.shape != ob.shape:
            raise ValueError(f"cell {cell}: side b has no upset array for its games: upset gate not judged")
        cell_upsets = int((up.astype(bool) & (ob != RUNNING)).sum())
        upsets += cell_upsets
        breach = {}
        for name, side, k, o in (("a", a, ka, oa), ("b", b, kb, ob)):
            fin = o != RUNNING
            breach[name] = float(side["per_game"][f"{k}|rule_breach"][fin].mean()) if fin.any() else None
        cells.append({
            "size": size, "guard": gs, "strike": ss, "band": band,
            "tier1": ha, "physics": hb, "hold_gap": gap, "hold_ok": hold_ok,
            "tier1_closest_3d_min_m": amin, "tier1_closest_3d_p05_m": ap05, "tier1_closest_games": an,
            "physics_closest_3d_min_m": bmin, "physics_closest_3d_p05_m": bp05, "physics_closest_games": bn,
            "closest_3d_min_gap_m": min_gap, "closest_3d_p05_gap_m": p05_gap, "closest_ok": closest_ok,
            "outcome_agreement": float((oa[both] == ob[both]).mean()) if both.any() else None,
            "mean_end_step_gap": float(eb[ob != RUNNING].mean() - ea[oa != RUNNING].mean())
            if (ob != RUNNING).any() and (oa != RUNNING).any() else None,
            "tier1_breach_rate": breach["a"], "physics_breach_rate": breach["b"],
            "start_miss_rate": float(a["per_game"][f"{ka}|start_miss"].mean()), "upset_games": cell_upsets})
    for m in b["metas"]:
        nan += int(m["physics"]["nonfinite_count"])               # present and an int: checked in _check_inputs
    upsets_ok = upsets <= int(gates["upsets_max"])
    nan_ok = nan <= int(gates["nan_max"])
    passed = bool(cells) and all(c["hold_ok"] and c["closest_ok"] for c in cells) and upsets_ok and nan_ok
    gaps = [abs(c["hold_gap"]) for c in cells if c["hold_gap"] is not None]
    mins = [c["closest_3d_min_gap_m"] for c in cells if c["closest_3d_min_gap_m"] is not None]
    p05s = [c["closest_3d_p05_gap_m"] for c in cells if c["closest_3d_p05_gap_m"] is not None]
    return {"verdict": "PASS" if passed else "FAIL", "preset_a": pa, "preset_b": pb, "local_file": "none",
            "gates": dict(gates), "cells": cells, "cells_total": len(cells),
            "cells_hold_fail": sum(not c["hold_ok"] for c in cells),
            "cells_closest_fail": sum(not c["closest_ok"] for c in cells),
            "largest_abs_hold_gap": max(gaps) if gaps else None,
            "largest_closest_3d_min_gap_m": max(mins) if mins else None,
            "largest_closest_3d_p05_gap_m": max(p05s) if p05s else None,
            "upsets": upsets, "upsets_ok": upsets_ok, "nan": nan, "nan_ok": nan_ok}


def config_problems(metas: list[dict], cfg: dict) -> list[str]:
    """Differences between the score runs (metas of one side) and ``[compare_games]``: strategies, sizes (the union
    over the side's folders), bands, games per band, seed, paired."""
    probs = []
    sizes = sorted({s for m in metas for s in m.get("sizes", [])})
    if sizes != sorted(cfg["sizes"]):
        probs.append(f"sizes {sizes} != {sorted(cfg['sizes'])}")
    for m in metas:
        for key in ("guards", "strikes"):
            if list(m.get(key, [])) != list(cfg[key]):
                probs.append(f"{key} {m.get(key)} != {cfg[key]}")
        if m.get("games_per_band") != cfg["games_per_band"]:
            probs.append(f"games_per_band {m.get('games_per_band')} != {cfg['games_per_band']}")
        if m.get("seed") != cfg["seed"]:
            probs.append(f"seed {m.get('seed')} != {cfg['seed']}")
        if bool(m.get("batch_per_pair")) != bool(cfg["batch_per_pair"]):
            probs.append("batch_per_pair differs")
        if list(m.get("bands", BAND_ORDER)) != list(BAND_ORDER):
            probs.append(f"bands {m.get('bands')} != {list(BAND_ORDER)}")
    return probs


def _f(v, nd=3) -> str:
    return "n/a" if v is None else f"{v:.{nd}f}"


def _pc(v) -> str:
    return "n/a" if v is None else f"{100 * v:.1f}"


def render_md(res: dict, meta: dict) -> str:
    g = res["gates"]
    lines = [f"# Paired scripted games: {res['preset_b']} against {res['preset_a']}", "",
             "Observed in the training simulator: tier 2 (Isaac Lab, physics drone) against tier 1 (Starling layer, "
             "exploratory drone model). Committed neutral values only (local file: none).", "",
             f"**Verdict: {res['verdict']}** against `[compare_games_gates]` ({meta['gates_file']}).", "",
             "| Gate | Limit | Measured | Result |", "|---|---|---|---|",
             f"| `max_cell_hold_gap` (every cell) | <= {g['max_cell_hold_gap']} | largest {_f(res['largest_abs_hold_gap'])}"
             f"; {res['cells_hold_fail']} of {res['cells_total']} cells over | "
             f"{'PASS' if res['cells_hold_fail'] == 0 else 'FAIL'} |",
             f"| `closest_cross_3d_gap_max_m` (every cell, min and p5) | <= {g['closest_cross_3d_gap_max_m']} | "
             f"largest min gap {_f(res['largest_closest_3d_min_gap_m'])}, p5 gap "
             f"{_f(res['largest_closest_3d_p05_gap_m'])}; {res['cells_closest_fail']} of {res['cells_total']} cells "
             f"over | {'PASS' if res['cells_closest_fail'] == 0 else 'FAIL'} |",
             f"| `upsets_max` | <= {g['upsets_max']} | {res['upsets']} | {'PASS' if res['upsets_ok'] else 'FAIL'} |",
             f"| `nan_max` | <= {g['nan_max']} | {res['nan']} | {'PASS' if res['nan_ok'] else 'FAIL'} |", "",
             "Hold rate in % with Wilson 95 % intervals; gap = physics - tier 1 (points). Closest = 3-D closest "
             "Guard-Strike approach per game, games without a start miss: minimum / 5th percentile (m); gap = tier 1 - "
             "physics (positive: the physics drones came closer). Agreement = share of paired slots with the same "
             "winner (INFO). End-step gap = physics - tier 1 mean game length in steps of 0.05 s (INFO).", "",
             "| size | Guard | Strike | band | tier 1 hold | physics hold | gap | tier 1 closest min / p5 | physics "
             "closest min / p5 | min gap / p5 gap | agreement | end-step gap | upsets | result |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in res["cells"]:
        t, p = c["tier1"], c["physics"]
        ok = c["hold_ok"] and c["closest_ok"]
        why = [] if ok else (["hold"] if not c["hold_ok"] else []) + (["closest"] if not c["closest_ok"] else [])
        lines.append(
            f"| {c['size']} | {c['guard']} | {c['strike']} | {c['band']} | {_pc(t['hold_rate'])} ({_pc(t['ci_low'])}–"
            f"{_pc(t['ci_high'])}) | {_pc(p['hold_rate'])} ({_pc(p['ci_low'])}–{_pc(p['ci_high'])}) | "
            f"{_pc(c['hold_gap'])} | {_f(c['tier1_closest_3d_min_m'])} / {_f(c['tier1_closest_3d_p05_m'])} | "
            f"{_f(c['physics_closest_3d_min_m'])} / {_f(c['physics_closest_3d_p05_m'])} | "
            f"{_f(c['closest_3d_min_gap_m'])} / {_f(c['closest_3d_p05_gap_m'])} | {_pc(c['outcome_agreement'])} | "
            f"{_f(c['mean_end_step_gap'], 1)} | {c['upset_games']} | {'PASS' if ok else 'FAIL (' + ', '.join(why) + ')'} |")
    lines += ["", f"Inputs: a = {', '.join(meta['a'])}; b = {', '.join(meta['b'])}.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--a", help="tier 1 score folder(s), comma list")
    ap.add_argument("--b", help="physics score folder(s), comma list")
    ap.add_argument("--gates", default=str(ROOT / "configs" / "s2b.toml"))
    ap.add_argument("--name", required=True)
    ap.add_argument("--runs-dir", default=str(ROOT / "runs"))
    ap.add_argument("--init", action="store_true", help="only write runs/<name>/gates.toml (before the score runs)")
    ap.add_argument("--no-config-check", action="store_true", help="tests only: skip the [compare_games] check")
    a = ap.parse_args(argv)
    cfg = tomllib.loads(pathlib.Path(a.gates).read_text())
    gates = cfg["compare_games_gates"]
    out = pathlib.Path(a.runs_dir) / a.name
    gates_text = (f"# Copied from {pathlib.Path(a.gates).name} [compare_games_gates] (owner-approved 16 November 2026; "
                  f"closest_cross_3d_gap_max_m = owner's decision A). Written "
                  f"{datetime.datetime.now().astimezone().isoformat(timespec='seconds')}.\n[compare_games_gates]\n"
                  + "".join(f"{k} = {json.dumps(v)}\n" for k, v in gates.items()))
    gates_path = out / "gates.toml"
    if gates_path.exists():
        held = tomllib.loads(gates_path.read_text()).get("compare_games_gates")
        if held != gates:
            print(f"refusing: {gates_path} holds other gates than {a.gates} (gates are never moved)", file=sys.stderr)
            return 2
    if a.init:
        if gates_path.exists():
            print(f"{gates_path} already written", flush=True)
            return 0
        out.mkdir(parents=True, exist_ok=True)
        gates_path.write_text(gates_text)
        print(f"wrote {gates_path}", flush=True)
        return 0
    if not (a.a and a.b):
        print("refusing: give --a and --b (or --init)", file=sys.stderr)
        return 2
    if (out / "compare.json").exists():
        print(f"refusing: {out / 'compare.json'} exists (a comparison is never overwritten)", file=sys.stderr)
        return 2
    dirs_a, dirs_b = [x.strip() for x in a.a.split(",") if x.strip()], [x.strip() for x in a.b.split(",") if x.strip()]
    try:
        side_a, side_b = load_side(dirs_a), load_side(dirs_b)
        if not a.no_config_check:
            probs = [f"a: {p}" for p in config_problems(side_a["metas"], cfg["compare_games"])]
            probs += [f"b: {p}" for p in config_problems(side_b["metas"], cfg["compare_games"])]
            if probs:
                raise ValueError("not the [compare_games] matchups: " + "; ".join(probs))
        res = compare(side_a, side_b, gates)
    except (ValueError, KeyError, FileNotFoundError) as e:
        print(f"refusing: {e}", file=sys.stderr)
        return 2
    meta = {"a": dirs_a, "b": dirs_b, "gates_file": pathlib.Path(a.gates).name,
            "config_check": "skipped (--no-config-check)" if a.no_config_check else "[compare_games] matched",
            "metas_a": side_a["metas"], "metas_b": side_b["metas"],
            "date": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
    out.mkdir(parents=True, exist_ok=True)
    if not gates_path.exists():
        gates_path.write_text(gates_text)
    (out / "compare.json").write_text(json.dumps({**res, "meta": meta}, indent=1))
    (out / "compare.md").write_text(render_md(res, meta))
    print(f"{res['verdict']}: {res['cells_hold_fail']} of {res['cells_total']} cells over the hold gap (largest "
          f"{_f(res['largest_abs_hold_gap'])}), {res['cells_closest_fail']} over the closest-approach gap; upsets "
          f"{res['upsets']}, NaN {res['nan']}. Wrote {out / 'compare.json'}, {out / 'compare.md'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
