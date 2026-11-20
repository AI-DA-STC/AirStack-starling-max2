#!/usr/bin/env python
"""L0.14 Crazyflie route check, part 1 (STE learning track; PLAN.md section 4): the STE Guard policy (T41) scored in its
own hangar game on the CPU with a slower drone response beside the Starling's. INFO: a sensitivity test, not a
Crazyflie model, no gate. Observed in the training simulator; nothing here is a flight result.

    cd <svg_training>; unset PYTHONPATH
    CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 PYTHONPATH=source \\
        ~/miniconda3/envs/env_isaaclab/bin/python scripts/ste_l014_response_check.py --run-dir runs/<date>_ste_l014/response

What it does, in order (settings: ``configs/ste_l014.toml [response]`` and ``[step_probe]``):

1. **Derived parameter files.** For each delay of ``delays_s``, a copy of ``base_params`` (the Starling's fitted response,
   T41's drone model) with the one line ``[px4] delay_s`` changed, written into the run folder with a SENSITIVITY header;
   the check reloads it and refuses if anything else differs. The game reads it through its existing ``starling.params``
   setting (``GameCfg.replace``): no default and no code of the game or the drone model changes.
2. **Control C-1 (bit for bit).** The default path (no settings change) and a derived file at the fitted delay play the
   first ``identity_games`` paired starts for ``identity_ticks`` ticks; every output (outcome, end step, closest approaches,
   rule breach, filter share, final positions and speeds) must be equal bit for bit, or the run stops (exit 6).
3. **Step probe.** One drone, no other drone, a constant ``speed_mps`` command from rest along x for ``duration_s``: how
   far the drone trails the commanded path (the command integrated), as a time (m / (m/s)), averaged from
   ``settle_from_s``. This says how late each cell's drone is, in the same terms as the Crazyflie notes (~0.56 s).
4. **Cells.** T41 (mean actions, one decision per 12 ticks) against S20 on the first ``games`` Phase 4 paired starts, with
   the evaluation seed and opponent seed of T41's own evaluation, once per delay. The reference cell is the default path
   (the base file itself). Per cell: hold rate with Wilson 95 %, games lost or gained against the reference (paired by
   start), closest Guard-Strike approach, rule-breach share, filter share, mean end step; per game in ``per_game.npz``.
5. ``results.json`` in the run folder (settings, sha256 of every file read, controls, cells, step traces, timings).

The delay applies to every drone in the game (both teams: an all-Crazyflie game), and the commander copy keeps the
Starling's leashes; a per-team delay would need code in the game (not built). Exit codes (ste/run_contract.py): 0 done,
2 refused, 6 a control failed."""
from __future__ import annotations

import argparse
import dataclasses
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

import numpy as np  # noqa: E402
import torch  # noqa: E402

CONFIG = ROOT / "configs" / "ste_l014.toml"
EXIT_OK, EXIT_REFUSED, EXIT_CONTROL_FAILED = 0, 2, 6
KEYS = {
    "response": {"guard_run", "opponent", "decision_ticks", "eval_seed", "opponent_seed_offset", "games", "base_params",
                 "fitted_delay_s", "delays_s", "identity_games", "identity_ticks"},
    "step_probe": {"speed_mps", "duration_s", "settle_from_s"},
    "arena_fit": {"cf_repo", "package", "arena_yaml", "python", "threads", "parallel", "seed0", "matches", "pairing", "matrix_seeds",
                  "tau_s", "rules", "strike_radius_m", "d_cc_m", "cc_z_ratio", "v_max_defense_mps", "v_max_attack_mps", "floor_m", "ceiling_m",
                  "vip_z_m", "defender_ring_m", "bearing0_deg", "attacker_ring_m", "sizes", "lag_check", "arenas",
                  "square_side_m", "matrix_arenas", "followup_sizes", "followup_arenas",
                  "followup_variants", "planner_strike_radius_m"},
}
RESULT_FIELDS = ("outcome", "end_step", "closest_cross_m", "closest_cross_3d_m", "rule_breach", "filter_corrected_rate",
                 "nonfinite_actions")
_DELAY = re.compile(r"^(delay_s\s*=\s*)(\S+)(.*)$", re.M)


def load_config(path: Path | str = CONFIG) -> dict:
    """The settings file as a dict; refuses (ValueError) a missing or unknown table or key."""
    data = tomllib.loads(Path(path).read_text())
    if set(data) != set(KEYS):
        raise ValueError(f"{path}: tables must be {sorted(KEYS)}, got {sorted(data)}")
    for table, want in KEYS.items():
        have = set(data[table])
        if have != want:
            raise ValueError(f"{path}: [{table}] unknown {sorted(have - want)}, missing {sorted(want - have)}")
    return data


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------------------ 1. derived files
def derive_params(base: Path | str, delay_s: float, out: Path | str) -> Path:
    """Write ``base`` with its one ``delay_s = ...`` line set to ``delay_s`` and a SENSITIVITY header; reload both and refuse
    (ValueError) unless they differ in ``[px4] delay_s`` only. Returns ``out``."""
    from svg_training.models.fitted import load_params
    base, out = Path(base), Path(out)
    text = base.read_text()
    hits = _DELAY.findall(text)
    if len(hits) != 1:
        raise ValueError(f"{base}: expected exactly one 'delay_s = ...' line, found {len(hits)}")
    old = hits[0][1]
    body = _DELAY.sub(lambda m: f"{m.group(1)}{delay_s!r}{m.group(3)}  [L0.14: was {old}]", text, count=1)
    head = (f"# L0.14 SENSITIVITY SET (not fitted, no source log): {base.name} (sha256 {sha256(base)[:16]}...) with "
            f"[px4] delay_s = {delay_s!r} instead of {old}.\n"
            "# Not a Crazyflie model and not a Starling fit: the same Starling response, made later by a pure delay on the\n"
            "# setpoint, to see how the STE Guard policy copes (ste_learning/CRAZYFLIE_ROUTE.md). Written by\n"
            "# scripts/ste_l014_response_check.py; everything below is the base file.\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(head + body)
    a, b = load_params(base), load_params(out)
    if b["px4"]["delay_s"] != float(delay_s):
        raise ValueError(f"{out}: delay_s reads {b['px4']['delay_s']}, not {delay_s}")
    b["px4"]["delay_s"] = a["px4"]["delay_s"]
    if a != b:
        raise ValueError(f"{out}: differs from {base} in more than [px4] delay_s")
    return out


# ------------------------------------------------------------------------------------------------ 3. step probe
def trailing(params: Path | str, speed_mps: float, duration_s: float, settle_from_s: float) -> dict:
    """One drone from rest at the origin, a constant command (speed_mps, 0, 0) for duration_s, no filter, no other drone.
    Returns t_s, x_m (flown), cmd_x_m (the command integrated: speed x t) and trailing_s = mean of (cmd_x - x) / speed
    over t >= settle_from_s."""
    from svg_training.core.game_config import TICK_S
    from svg_training.models.fitted import FittedResponse
    model = FittedResponse(1, 1, params, device="cpu", safety_filter=False, hover_seed=True,
                           pos_m=torch.zeros(1, 1, 3))
    model.reset(torch.ones(1, 1, dtype=torch.bool), torch.zeros(1, 1, 3))
    cmd = torch.tensor([[[speed_mps, 0.0, 0.0]]])
    steps = round(duration_s / TICK_S)
    xs = []
    for _ in range(steps):                     # one drone, a fixed number of ticks: not a loop over games
        model.step(cmd)
        xs.append(model.pos_m[0, 0, 0].clone())
    x = torch.stack(xs).double().numpy()
    t = np.arange(1, steps + 1) * TICK_S
    cmd_x = speed_mps * t
    late = (cmd_x - x) / speed_mps
    return {"t_s": t.tolist(), "x_m": x.tolist(), "cmd_x_m": cmd_x.tolist(),
            "trailing_s": float(late[t >= settle_from_s - 1e-9].mean())}


# ------------------------------------------------------------------------------------------------ 2./4. the games
def play(cfg: dict, params: Path | None, games: int, max_steps: int | None = None) -> dict:
    """T41 v the opponent on the first ``games`` Phase 4 paired starts, CPU, T41's evaluation seeds. ``params`` None = the
    default path (the game's settings untouched); else the game's ``starling.params`` points at that file. Returns the
    MatchResult fields of RESULT_FIELDS plus pos_m and vel_mps (the game's final state) as CPU tensors, and steps."""
    from svg_training.core.play import play_match
    from svg_training.nus import pilot as P
    from svg_training.opponents.learned import SkrlPolicyStrategy
    world = P.pilot_world(0.0)                       # shaping weight: reward only, no effect on play
    if params is not None:
        world = dataclasses.replace(world, cfg=world.cfg.replace(**{"starling.params": str(params)}))
    seed = int(cfg["eval_seed"])
    _, evals = P.pilot_games(world, 1, [games], "cpu", seed, seed)
    game = evals[games]
    opp = P.mix_strategy([(cfg["opponent"], slice(0, games))], "strike", world.cfg, "cpu", seed + int(cfg["opponent_seed_offset"]))
    guard = P.HeldStrategy(SkrlPolicyStrategy(ROOT / cfg["guard_run"], games, "cpu"), P.decision_ticks(cfg["decision_ticks"], world))
    game.gen.manual_seed(seed)
    res = play_match(game, guard, opp, max_steps=max_steps)
    out = {k: getattr(res, k).detach().cpu().clone() for k in RESULT_FIELDS}
    out.update(pos_m=game.pos_m.detach().cpu().clone(), vel_mps=game.vel_mps.detach().cpu().clone(), steps=res.steps_played)
    return out


def identical(a: dict, b: dict) -> list[str]:
    """Names of the outputs that differ (empty = every output equal bit for bit)."""
    return [k for k in (*RESULT_FIELDS, "pos_m", "vel_mps") if not torch.equal(a[k], b[k])] + (
        ["steps"] if a["steps"] != b["steps"] else [])


def paired(ref_outcome: np.ndarray, cell_outcome: np.ndarray) -> dict:
    """Games held in both, lost in the cell only, gained in the cell only, lost in both (paired by start)."""
    from svg_training.core.rewards import GUARD_WIN, RUNNING
    ref, cell = np.asarray(ref_outcome), np.asarray(cell_outcome)
    if ref.shape != cell.shape:
        raise ValueError(f"paired games differ in number: {ref.shape} v {cell.shape}")
    if (ref == RUNNING).any() or (cell == RUNNING).any():
        raise ValueError("a game did not finish: paired counts need finished games")
    r, c = ref == GUARD_WIN, cell == GUARD_WIN
    return {"both_hold": int((r & c).sum()), "lost_here": int((r & ~c).sum()), "gained_here": int((~r & c).sum()),
            "both_lost": int((~r & ~c).sum()), "games": int(ref.size)}


def summary(out: dict) -> dict:
    from svg_training.core.metrics import wilson_interval
    from svg_training.core.rewards import GUARD_WIN, RUNNING
    oc = out["outcome"].numpy()
    fin = oc != RUNNING
    n, k = int(fin.sum()), int((oc == GUARD_WIN).sum())
    c3 = out["closest_cross_3d_m"].numpy()[fin]
    c2 = out["closest_cross_m"].numpy()[fin]
    c3, c2 = c3[np.isfinite(c3)], c2[np.isfinite(c2)]
    return {"games": n, "unfinished": int((~fin).sum()), "holds": k, "hold": k / n if n else None,
            "ci": list(wilson_interval(k, n)), "mean_end_step": float(out["end_step"].numpy()[fin].mean()),
            "closest_3d_min_m": float(c3.min()) if c3.size else None,
            "closest_3d_median_m": float(np.median(c3)) if c3.size else None,
            "closest_xy_min_m": float(c2.min()) if c2.size else None,
            "rule_breach_share": float(out["rule_breach"].numpy()[fin].mean()),
            "filter_share": float(out["filter_corrected_rate"].numpy()[fin].mean()),
            "nonfinite_actions": int(out["nonfinite_actions"].sum())}


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout.strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run-dir", required=True, help="output folder under runs/")
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--games", type=int, default=None, help="override [response] games (smoke only; stamped in results)")
    ap.add_argument("--max-steps", type=int, default=None, help="cap the cells' ticks (smoke only; stamped in results)")
    a = ap.parse_args(argv)
    run = Path(a.run_dir).resolve()
    if (ROOT / "runs").resolve() not in run.parents:
        print(f"refusing: {run} is not under {ROOT / 'runs'}", file=sys.stderr)
        return EXIT_REFUSED
    if (run / "results.json").exists():
        print(f"refusing: {run / 'results.json'} exists (one run per folder)", file=sys.stderr)
        return EXIT_REFUSED
    cfg_all = load_config(a.config)
    cfg, probe = cfg_all["response"], cfg_all["step_probe"]
    from svg_training.models.fitted import load_params
    base = ROOT / cfg["base_params"]
    if load_params(base)["px4"]["delay_s"] != cfg["fitted_delay_s"]:
        print(f"refusing: {base} delay_s is not fitted_delay_s {cfg['fitted_delay_s']}", file=sys.stderr)
        return EXIT_REFUSED
    if cfg["fitted_delay_s"] not in cfg["delays_s"]:
        print("refusing: the reference cell (fitted_delay_s) must be one of delays_s", file=sys.stderr)
        return EXIT_REFUSED
    games = int(a.games or cfg["games"])
    smoke = a.games is not None or a.max_steps is not None
    run.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    files = {d: derive_params(base, d, run / "params" / f"delay_{d:.4f}s.toml") for d in cfg["delays_s"]}
    res: dict = {"what": "L0.14 part 1, INFO (no gate): T41 v S20 in T41's hangar game, CPU, a slower drone beside the "
                         "Starling's. Observed in the training simulator; a sensitivity test, not a Crazyflie model.",
                 "smoke_not_of_record": smoke, "config": str(Path(a.config).relative_to(ROOT)) if Path(a.config).resolve().is_relative_to(ROOT) else a.config,
                 "config_sha256": sha256(Path(a.config)), "settings": {"response": cfg, "step_probe": probe},
                 "games": games, "max_steps": a.max_steps, "git_commit": git("rev-parse", "--short", "HEAD"),
                 "git_dirty": bool(git("status", "--porcelain")), "machine": platform.node(), "device": "cpu",
                 "torch": torch.__version__, "threads": torch.get_num_threads(),
                 "files": {"base_params": {"path": cfg["base_params"], "sha256": sha256(base)},
                           "guard_agent": {"path": f"{cfg['guard_run']}/agent.pt", "sha256": sha256(ROOT / cfg["guard_run"] / "agent.pt")},
                           **{f"derived_{d}": {"path": str(p.relative_to(ROOT)), "sha256": sha256(p)} for d, p in files.items()}}}

    # ---- C-1: the default path and a derived file at the fitted delay, bit for bit on game outputs
    t0 = time.perf_counter()
    k, ticks = int(cfg["identity_games"]), int(cfg["identity_ticks"])
    diff = identical(play(cfg, None, k, ticks), play(cfg, files[cfg["fitted_delay_s"]], k, ticks))
    res["controls"] = {"C-1 bit for bit": {"games": k, "ticks": ticks, "differs": diff, "verdict": "PASS" if not diff else "FAIL",
                                           "seconds": time.perf_counter() - t0}}
    print(f"[C-1] {k} games x {ticks} ticks, default path v derived file at the fitted delay: "
          f"{'PASS (every output equal)' if not diff else 'FAIL: ' + ', '.join(diff)}", flush=True)
    if diff:
        (run / "results.json").write_text(json.dumps(res, indent=1))
        return EXIT_CONTROL_FAILED

    # ---- step probe
    res["step"] = [{"delay_s": d, **trailing(p, probe["speed_mps"], probe["duration_s"], probe["settle_from_s"])}
                   for d, p in files.items()]
    for s in res["step"]:
        print(f"[step] delay {s['delay_s']:.4f} s: trails the commanded path by {s['trailing_s']:.3f} s", flush=True)

    # ---- cells
    per_game: dict[str, np.ndarray] = {}
    cells, ref = [], None
    for d in cfg["delays_s"]:
        t0 = time.perf_counter()
        out = play(cfg, None if d == cfg["fitted_delay_s"] else files[d], games, a.max_steps)
        cell = {"delay_s": d, "path": "default (base file)" if d == cfg["fitted_delay_s"] else str(files[d].relative_to(ROOT)),
                **summary(out), "trailing_s": next(s["trailing_s"] for s in res["step"] if s["delay_s"] == d),
                "seconds": time.perf_counter() - t0, "steps": out["steps"]}
        for key in RESULT_FIELDS:
            per_game[f"delay_{d:.4f}__{key}"] = out[key].numpy()
        if d == cfg["fitted_delay_s"]:
            ref = out["outcome"].numpy()
        cells.append(cell)
        print(f"[cell] delay {d:.4f} s: hold {cell['holds']}/{cell['games']} = {cell['hold']:.3f} "
              f"[{cell['ci'][0]:.3f}, {cell['ci'][1]:.3f}], {cell['unfinished']} unfinished, {cell['seconds']:.0f} s", flush=True)
    finished = all(c["unfinished"] == 0 for c in cells)
    for c in cells:
        c["paired"] = paired(ref, per_game[f"delay_{c['delay_s']:.4f}__outcome"]) if finished else None
    res["cells"] = cells
    res["reference_cell"] = [c["delay_s"] for c in cells].index(cfg["fitted_delay_s"])
    res["controls"]["C-2 every game finished, no non-finite action"] = {
        "verdict": "PASS" if finished and all(c["nonfinite_actions"] == 0 for c in cells) else "FAIL"}
    res["seconds"] = time.time() - t_start
    np.savez_compressed(run / "per_game.npz", **per_game)
    (run / "results.json").write_text(json.dumps(res, indent=1))
    print(f"wrote {run / 'results.json'} ({res['seconds']:.0f} s)")
    return EXIT_OK if res["controls"]["C-2 every game finished, no non-finite action"]["verdict"] == "PASS" else EXIT_CONTROL_FAILED


if __name__ == "__main__":
    sys.exit(main())
