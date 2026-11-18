#!/usr/bin/env python
"""Parity of the batched safety-filter port against CMU's cbf_filter.py, on seeded random scenes.

Run of record:  filter_parity.py --gates configs/s1.toml --name <YYYY-MM-DD>_s1_filter_parity
  writes records/<name>_record.md and appends one T<n> row to records/LEDGER.md; refuses to overwrite.
Iteration sweep (design aid, writes nothing):  filter_parity.py --gates configs/s1.toml --sweep 20,60,200 --seed 1

The original is imported read-only from ../AirStack/robot/ros_ws/src/svg_ground_control and called one
scene at a time; a two-team scene calls it once per team (the team-masked reference). The port runs all
scenes in one batch on the CPU. Exit 0 when the record was written (whatever the verdict), 1 on refusal.
"""
import argparse
import hashlib
import os
import platform
import re
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
CMU_FILE_REL = "AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/cbf_filter.py"
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(REPO / "AirStack/robot/ros_ws/src/svg_ground_control"))

from svg_ground_control.cbf_filter import filter_velocities as cmu_filter  # noqa: E402
from svg_training.core.safety_filter import filter_velocities  # noqa: E402

RADIUS_M = 0.55
ALPHA = 2.5
TOL = 2e-3
M_MAX = 8
NEAR_M = 2 * RADIUS_M * 1.5  # near-collision pair distance
KEEP_OUT_M = 2 * RADIUS_M
SIMULATOR = "Simulator: training simulator (safety-filter port vs CMU cbf_filter.py, CPU)"
DEFAULT_SEED = 20261115


@dataclass
class Scene:
    """One scene: pos_m, nominal_mps (M, 3); team (M,) 0 or 1; max_speed_mps; teams 1 or 2."""

    pos_m: np.ndarray
    nominal_mps: np.ndarray
    team: np.ndarray
    max_speed_mps: float
    teams: int


def _unit(rng):
    u = rng.normal(size=3)
    return u / np.linalg.norm(u)


def make_scenes(count: int, seed: int) -> list:
    """Seeded scenes: 2-8 drones, 1 or 2 teams, near-collision heavy, head-on approaches, some penetration."""
    scenes = []
    for k in range(count):
        rng = np.random.default_rng([seed, k])
        m = int(rng.integers(2, M_MAX + 1))
        vmax = float(rng.uniform(1.0, 4.0))
        pos = np.zeros((m, 3))
        pos[0] = rng.uniform([-2, -2, 0.5], [2, 2, 2.5])
        for d in range(1, m):
            u = rng.random()
            other = int(rng.integers(d))
            if u < 0.02:  # coincident with another drone
                pos[d] = pos[other]
            elif u < 0.65:  # near another drone: inside the keep-out (30 %) or in the near band
                dist = rng.uniform(0.3, KEEP_OUT_M) if rng.random() < 0.3 else rng.uniform(KEEP_OUT_M, NEAR_M)
                pos[d] = pos[other] + _unit(rng) * dist
            else:
                pos[d] = rng.uniform([-2, -2, 0.5], [2, 2, 2.5])
        speed = rng.uniform(0.0, 1.0, size=m) * vmax
        nom = np.stack([_unit(rng) for _ in range(m)]) * speed[:, None]
        for i in range(m):  # head-on approaches on half of the near pairs
            for j in range(i + 1, m):
                rel = pos[i] - pos[j]
                dist = np.linalg.norm(rel)
                if 1e-9 < dist < NEAR_M and rng.random() < 0.5:
                    s = rng.uniform(0.3, 1.0) * vmax
                    nom[i] = -rel / dist * s
                    nom[j] = rel / dist * s
        teams = 2 if rng.random() < 0.5 else 1
        team = np.zeros(m, dtype=int)
        if teams == 2:
            team[rng.permutation(m)[: int(rng.integers(1, m))]] = 1
        scenes.append(Scene(pos, nom, team, vmax, teams))
    return scenes


def _pairs(s: Scene):
    m = len(s.pos_m)
    for i in range(m):
        for j in range(i + 1, m):
            yield i, j, float(np.linalg.norm(s.pos_m[i] - s.pos_m[j])), bool(s.team[i] == s.team[j])


def scene_stats(scenes: list) -> dict:
    near_scene = pen_scene = coinc = pairs = near_pairs = 0
    within = within_near = 0
    for s in scenes:
        p = list(_pairs(s))
        pairs += len(p)
        near_pairs += sum(d < NEAR_M for _, _, d, _ in p)
        within += sum(w for *_, w in p)
        within_near += sum(w and d < NEAR_M for _, _, d, w in p)
        near_scene += any(d < NEAR_M for _, _, d, _ in p)
        pen_scene += any(d < KEEP_OUT_M for _, _, d, _ in p)
        coinc += any(d < 1e-9 for _, _, d, _ in p)
    return {
        "scenes": len(scenes),
        "one_team_scenes": sum(s.teams == 1 for s in scenes),
        "two_team_scenes": sum(s.teams == 2 for s in scenes),
        "drones_histogram": {m: sum(len(s.pos_m) == m for s in scenes) for m in range(2, M_MAX + 1)},
        "near_scene_fraction": near_scene / len(scenes),
        "near_pair_fraction": near_pairs / max(pairs, 1),
        "within_team_near_pair_fraction": within_near / max(within, 1),
        "penetration_scenes": pen_scene,
        "coincident_scenes": coinc,
    }


def run_original(scenes: list) -> dict:
    """CMU's filter one scene (and one team) at a time."""
    vel, emerg, conv, sweeps = [], [], [], []
    t0 = time.perf_counter()
    for s in scenes:
        v = np.zeros_like(s.nominal_mps)
        e, c, it = False, True, 0
        for t in range(s.teams):
            idx = np.flatnonzero(s.team == t)
            r = cmu_filter(s.nominal_mps[idx], s.pos_m[idx], safety_radius=RADIUS_M, max_speed=s.max_speed_mps,
                           alpha=ALPHA)
            v[idx] = r.velocities
            e, c, it = e or r.used_emergency_stop, c and r.converged, max(it, r.iterations)
        vel.append(v)
        emerg.append(e)
        conv.append(c)
        sweeps.append(it)
    return {"vel": vel, "emergency": np.array(emerg), "converged": np.array(conv), "sweeps": np.array(sweeps),
            "seconds": time.perf_counter() - t0}


def _batch(scenes: list, only_team=None, dtype=torch.float32):
    """Pad scenes to M_MAX drones. only_team: per-scene team to keep (the other team is padded out)."""
    n = len(scenes)
    pos = np.zeros((n, M_MAX, 3))
    pos[:, :, 0] = 100.0 + 10.0 * np.arange(M_MAX)  # padding drones: far apart, masked anyway
    nom = np.zeros((n, M_MAX, 3))
    mask = np.zeros((n, M_MAX, M_MAX), dtype=bool)
    cap = np.zeros((n, 1, 1))
    for k, s in enumerate(scenes):
        keep = np.ones(len(s.pos_m), bool) if only_team is None else s.team == only_team[k]
        idx = np.flatnonzero(keep)
        pos[k, idx], nom[k, idx] = s.pos_m[idx], s.nominal_mps[idx]
        same = (s.team[idx, None] == s.team[None, idx]) & ~np.eye(len(idx), dtype=bool)
        mask[k][np.ix_(idx, idx)] = same
        cap[k] = s.max_speed_mps
    t = lambda a: torch.tensor(a, dtype=dtype)  # noqa: E731
    return t(nom), t(pos), torch.tensor(mask), t(cap)


def run_port(scenes: list, iterations: int, dtype=torch.float32, only_team=None, **filter_kw) -> dict:
    """The port on all scenes in one CPU batch. filter_kw (e.g. ``check_every``, S2 Task 7) goes to
    ``filter_velocities``; without it the call is run T2's."""
    nom, pos, mask, cap = _batch(scenes, only_team, dtype)
    t0 = time.perf_counter()
    res = filter_velocities(nom, pos, mask, RADIUS_M, cap, alpha=ALPHA, iterations=iterations, tolerance=TOL,
                            **filter_kw)
    sec = time.perf_counter() - t0
    v = res.velocities.double().numpy()
    return {"vel": [v[k, : len(s.pos_m)] for k, s in enumerate(scenes)], "emergency": res.emergency.numpy(),
            "seconds": sec}


def worst_constraint_violation(s: Scene, v: np.ndarray) -> float:
    """Every within-team pair constraint and the speed cap of the scene, at velocities v."""
    worst = float(np.max(np.maximum(0.0, np.linalg.norm(v, axis=-1) - s.max_speed_mps)))
    for i, j, _, w in _pairs(s):
        if w:
            rel = s.pos_m[i] - s.pos_m[j]
            lhs = 2.0 * rel @ (v[i] - v[j]) + ALPHA * (rel @ rel - (2 * RADIUS_M) ** 2)
            worst = max(worst, -lhs)
    return worst


def cross_team_check(scenes: list, port: dict, iterations: int, dtype, **filter_kw) -> dict:
    """Port with both teams vs the port with the other team removed: any change is a cross-team correction.
    filter_kw goes to ``run_port`` (the same settings as ``port``); without it the check is run T2's."""
    two = [k for k, s in enumerate(scenes) if s.teams == 2]
    sub = [scenes[k] for k in two]
    alone = {t: run_port(sub, iterations, dtype, only_team=[t] * len(sub), **filter_kw) for t in (0, 1)}
    corrections = pairs = closing = 0
    for q, k in enumerate(two):
        s = scenes[k]
        changed = np.zeros(len(s.pos_m), bool)
        for t in (0, 1):
            idx = s.team == t
            changed[idx] = np.any(port["vel"][k][idx] != alone[t]["vel"][q][idx], axis=-1)
        for i, j, _, w in _pairs(s):
            if not w:
                pairs += 1
                rel = s.pos_m[i] - s.pos_m[j]
                lhs = 2 * rel @ (s.nominal_mps[i] - s.nominal_mps[j]) + ALPHA * (rel @ rel - (2 * RADIUS_M) ** 2)
                closing += lhs < 0
                corrections += bool(changed[i] or changed[j])
    return {"cross_team_corrections": corrections, "cross_team_pairs": pairs, "cross_team_pairs_violating": closing}


def evaluate(scenes, ref, port) -> dict:
    """Gate quantities. S = scenes where the original converged without emergency."""
    s_idx = np.flatnonzero(ref["converged"] & ~ref["emergency"])
    dv = np.array([np.max(np.abs(port["vel"][k] - ref["vel"][k])) for k in range(len(scenes))])
    resid = np.array([worst_constraint_violation(scenes[k], port["vel"][k]) for k in range(len(scenes))])
    agree = port["emergency"] == ref["emergency"]
    both = np.flatnonzero(port["emergency"] & ref["emergency"])
    gs = ref["sweeps"][s_idx] > 200  # the original needed its Gauss-Seidel polish
    ref_resid = np.array([worst_constraint_violation(scenes[k], ref["vel"][k]) for k in s_idx])
    return {
        "subset": s_idx, "dv": dv, "resid": resid,
        "subset_gs": int(gs.sum()),
        "max_dv_subset_no_gs": float(dv[s_idx[~gs]].max()) if (~gs).any() else 0.0,
        "max_dv_subset_gs": float(dv[s_idx[gs]].max()) if gs.any() else 0.0,
        "ref_resid_max": float(ref_resid.max()) if len(ref_resid) else 0.0,
        "ref_resid_over": int((ref_resid > TOL).sum()),
        "max_abs_dv_mps": float(dv[s_idx].max()) if len(s_idx) else 0.0,
        "constraint_residual_max": float(resid[s_idx].max()) if len(s_idx) else 0.0,
        "emergency_agreement_min": float(agree.mean()),
        "emergency_disagree": np.flatnonzero(~agree),
        "both_emergency_max_dv": float(dv[both].max()) if len(both) else 0.0,
        "both_emergency": len(both),
    }


def verdicts(gates: dict, ev: dict, cross: dict) -> list:
    rows = [
        ("max_abs_dv_mps", ev["max_abs_dv_mps"], gates["max_abs_dv_mps"], ev["max_abs_dv_mps"] <= gates["max_abs_dv_mps"],
         "<="),
        ("constraint_residual_max", ev["constraint_residual_max"], gates["constraint_residual_max"],
         ev["constraint_residual_max"] <= gates["constraint_residual_max"], "<="),
        ("emergency_agreement_min", ev["emergency_agreement_min"], gates["emergency_agreement_min"],
         ev["emergency_agreement_min"] >= gates["emergency_agreement_min"], ">="),
        ("cross_team_corrections", cross["cross_team_corrections"], gates["cross_team_corrections"],
         cross["cross_team_corrections"] <= gates["cross_team_corrections"], "<="),
    ]
    return rows


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args) -> str:
    try:
        return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _cpu() -> str:
    try:
        for ln in Path("/proc/cpuinfo").read_text().splitlines():
            if ln.startswith("model name"):
                return ln.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def _fmt(x) -> str:
    return f"{x:.6g}" if isinstance(x, float) else str(x)


def write_record(path: Path, a, gates_path: Path, gates: dict, scenes, stats, ref, port, ev, cross, rows,
                 date: str) -> str:
    overall = "PASS" if all(r[3] for r in rows) else "FAIL"
    worst = sorted(ev["subset"], key=lambda k: -ev["dv"][k])[:5]
    lines = [
        SIMULATOR, "", f"# {date} {a.name} record", "",
        "## Purpose", "",
        "Check that the batched safety-filter port (`source/svg_training/core/safety_filter.py`) gives the same "
        "velocities and the same emergency decisions as CMU's `cbf_filter.py`, and that Guard–Strike pairs get "
        f"no correction. Overall result: **{overall}**.", "",
        "## Original", "",
        f"`{CMU_FILE_REL}`, git blob `{_git('rev-parse', 'HEAD:' + CMU_FILE_REL)}`, "
        f"sha256 `{_sha(REPO / CMU_FILE_REL)}`; called one scene at a time (once per team in two-team scenes), "
        "defaults `max_iterations` 200, `tolerance` 2e-3, no `fixed` rows.", "",
        "## Commit", "",
        f"Repository HEAD `{_git('rev-parse', 'HEAD')}`. Port sha256 "
        f"`{_sha(ROOT / 'source/svg_training/core/safety_filter.py')[:12]}`, script sha256 `{_sha(Path(__file__))[:12]}`.", "",
        "## Config", "",
        f"`{gates_path}`, sha256 `{_sha(gates_path)}`, table `[filter_gates]`.", "",
        "## Settings", "",
        f"Port: `iterations` {a.iterations}, `tolerance` {TOL}, dtype {a.dtype}, device CPU "
        f"({torch.get_num_threads()} threads). Both: safety radius {RADIUS_M} m, alpha {ALPHA}, speed cap per scene. "
        "Port emergency rule: non-finite row, coincident pair, or residual after the clamp > 5 x tolerance "
        "(the original also acts when its solver did not converge; see the port's docstring).", "",
        "## Seeds", "",
        f"Scene seed {a.seed}; scene k uses `numpy.random.default_rng([{a.seed}, k])`.", "",
        "## Scenes", "",
        f"{stats['scenes']} scenes: {stats['one_team_scenes']} one team, {stats['two_team_scenes']} two teams "
        f"(random split). Drones per scene: "
        + ", ".join(f"{m}: {c}" for m, c in stats["drones_histogram"].items()) + ". "
        f"Scenes with a pair closer than {NEAR_M:.2f} m: {stats['near_scene_fraction']:.1%}; pairs that close: "
        f"{stats['near_pair_fraction']:.1%} (within a team: {stats['within_team_near_pair_fraction']:.1%}). "
        f"Scenes with a pair inside the {KEEP_OUT_M:.2f} m keep-out: {stats['penetration_scenes']}; with coincident "
        f"drones: {stats['coincident_scenes']}. Speed cap 1.0–4.0 m/s; nominal speeds up to the cap, head-on on "
        "half of the near pairs.", "",
        f"Original: converged without emergency in {len(ev['subset'])} scenes (subset S), emergency in "
        f"{int(ref['emergency'].sum())}, Gauss-Seidel polish needed in {int((ref['sweeps'] > 200).sum())}; "
        f"most sweeps in one call {int(ref['sweeps'].max())}. Port: emergency in {int(port['emergency'].sum())}.", "",
        "## Machine", "",
        f"{_cpu()}; torch {torch.__version__}, numpy {np.__version__}, Python {platform.python_version()}.", "",
        "## Gates", "",
        "`max_abs_dv_mps` and `constraint_residual_max` are taken over subset S (every within-team pair constraint "
        "and the speed cap, recomputed in float64 from the port's velocities). `emergency_agreement_min` is over all "
        "scenes. `cross_team_corrections` counts Guard–Strike pairs whose drones' velocities change at all when the "
        "other team is removed from the game.", "",
        "| Gate | Measured | Limit (FIXED) | Result |", "|---|---|---|---|",
    ]
    for name, meas, lim, ok, op in rows:
        lines.append(f"| `{name}` | {_fmt(meas)} | {op} {_fmt(lim)} | {'PASS' if ok else 'FAIL'} |")
    lines += [
        "",
        f"Cross-team pairs checked: {cross['cross_team_pairs']}, of which {cross['cross_team_pairs_violating']} "
        "violate their constraint at the nominal velocities (they would be corrected without the team mask).",
        "",
        f"Context (informational, not gates): in {ev['subset_gs']} scenes of S the original needed its Gauss-Seidel "
        f"polish, which the port does not have; largest |Δv| there {ev['max_dv_subset_gs']:.3g} m/s, on the rest of S "
        f"{ev['max_dv_subset_no_gs']:.3g} m/s. The original's own worst constraint residual on S is "
        f"{ev['ref_resid_max']:.3g} ({ev['ref_resid_over']} scenes above {TOL}): it tests convergence before its "
        "final speed clamp.",
        f"Scenes where both used the emergency push-apart: {ev['both_emergency']}; largest velocity difference there "
        f"{ev['both_emergency_max_dv']:.3g} m/s (informational: the port evaluates every pair on the pre-push "
        "velocities, the original pair by pair).", "",
        "## Worst scenes (subset S, by max |Δv|)", "",
        "| Scene | Drones | Teams | Speed cap (m/s) | Original sweeps | max abs dv (m/s) | Port residual | "
        "Original residual |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for k in worst:
        s = scenes[k]
        lines.append(f"| {k} | {len(s.pos_m)} | {s.teams} | {s.max_speed_mps:.2f} | {ref['sweeps'][k]} | "
                     f"{ev['dv'][k]:.3g} | {ev['resid'][k]:.3g} | "
                     f"{worst_constraint_violation(s, ref['vel'][k]):.3g} |")
    dis = ev["emergency_disagree"]
    lines += ["", "## Emergency disagreements", "",
              f"{len(dis)} scenes" + (": " + ", ".join(
                  f"{k} (original {'yes' if ref['emergency'][k] else 'no'}, port {'yes' if port['emergency'][k] else 'no'}, "
                  f"original sweeps {ref['sweeps'][k]})" for k in dis[:20]) if len(dis) else "") + ".", "",
              "## Timing (informational)", "",
              f"Original, one call at a time: {ref['seconds']:.2f} s for {len(scenes)} scenes. "
              f"Port, one batch of {len(scenes)} games x {M_MAX} drones: {port['seconds']:.3f} s.", ""]
    path.write_text("\n".join(lines))
    return overall


def sweep(a, gates):
    scenes = make_scenes(gates["scenes"], a.seed)
    ref = run_original(scenes)
    print(f"seed {a.seed}, {len(scenes)} scenes; original: S={int((ref['converged'] & ~ref['emergency']).sum())}, "
          f"emergency {int(ref['emergency'].sum())}, GS {int((ref['sweeps'] > 200).sum())}, "
          f"max sweeps {int(ref['sweeps'].max())}")
    print("| iterations | max abs dv on S (m/s) | max residual on S | emergency agreement | port emergencies | "
          "port seconds |")
    print("|---|---|---|---|---|---|")
    for k in [int(x) for x in a.sweep.split(",")]:
        port = run_port(scenes, k, getattr(torch, a.dtype))
        ev = evaluate(scenes, ref, port)
        print(f"| {k} | {ev['max_abs_dv_mps']:.4g} | {ev['constraint_residual_max']:.3g} | "
              f"{ev['emergency_agreement_min']:.4f} | {int(port['emergency'].sum())} | {port['seconds']:.3f} |")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--gates", required=True)
    p.add_argument("--name", default=None)
    p.add_argument("--iterations", type=int, default=1000)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--dtype", default="float32", choices=["float32", "float64"])
    p.add_argument("--sweep", default=None, help="comma-separated iteration counts: print a table, write nothing")
    p.add_argument("--out-dir", default=str(ROOT / "records"))
    p.add_argument("--ledger", default=str(ROOT / "records" / "LEDGER.md"))
    a = p.parse_args(argv)
    gates_path = Path(a.gates).resolve()
    gates = tomllib.loads(gates_path.read_text())["filter_gates"]
    torch.set_num_threads(min(8, torch.get_num_threads()))  # more threads were 25x slower on the laptop
    if a.sweep:
        return sweep(a, gates)
    if not a.name:
        p.error("--name is required unless --sweep is given")
    out = Path(a.out_dir) / f"{a.name}_record.md"
    ledger = Path(a.ledger)
    if out.exists():
        print(f"refusing to overwrite {out}", file=sys.stderr)
        return 1
    if not os.access(ledger, os.W_OK):
        print(f"ledger not writable: {ledger}", file=sys.stderr)
        return 1
    date = datetime.now().astimezone().isoformat(timespec="seconds")
    dtype = getattr(torch, a.dtype)
    scenes = make_scenes(gates["scenes"], a.seed)
    stats = scene_stats(scenes)
    ref = run_original(scenes)
    port = run_port(scenes, a.iterations, dtype)
    ev = evaluate(scenes, ref, port)
    cross = cross_team_check(scenes, port, a.iterations, dtype)
    rows = verdicts(gates, ev, cross)
    if out.exists():
        print(f"refusing to overwrite {out}", file=sys.stderr)
        return 1
    overall = write_record(out, a, gates_path, gates, scenes, stats, ref, port, ev, cross, rows, date)
    text = ledger.read_text()
    # next number after the highest T row (numbers are never reused, so a gap such as an unused T34 must not shift it)
    n = 1 + max((int(t) for t in re.findall(r"^\| T(\d+) \|", text, flags=re.M)), default=0)
    if not text.endswith("\n"):
        text += "\n"
    ledger.write_text(text + f"| T{n} | {date} | training simulator (safety-filter port vs CMU cbf_filter.py, CPU) | "
                      f"{a.name} | S1 safety-filter parity, {gates['scenes']} scenes, {a.iterations} sweeps | "
                      f"{overall} | records/{out.name} |\n")
    for name, meas, lim, ok, op in rows:
        print(f"{name}: {_fmt(meas)} (limit {op} {_fmt(lim)}) {'PASS' if ok else 'FAIL'}")
    print(f"wrote {out}; ledger T{n}; overall {overall}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
