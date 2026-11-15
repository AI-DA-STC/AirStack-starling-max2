#!/usr/bin/env python
"""Wall-limit probe: why scripted Guard-Strike pairs still come 0.75-0.80 m apart (keep-out 1.10 m) with the
Starling layer on, in crowded 5v3 games, after the wall fix (T9 record, Limits).

  probe_wall_limit.py [--variants baseline,wall_aware,ideal_model,wall_aware_ideal] [--n 300] [--band 0]
                      [--threads 6]

Plays guard_mirror v strike_flank, 5 v 3, Starling layer on, on the CPU, with the committed neutral game settings
(never the partner's local file), 1,000 filter sweeps with a check every 8 (T9's setting), game seed = band index,
strategy seeds 101 / 202. Each game slot counts its first game only; games that began with a start miss are left
out. Variants (any subset, in order):

  baseline          the committed layer, as T9 ran it.
  wall_aware        the safety filter also knows the walls: a drone held at a wall may not be told to move further
                    out (one more projection set in the filter). The filter is built here from the committed
                    core/safety_filter.py plus a small patch (WALL_PATCH below); the core is not changed.
  ideal_model       the drone does exactly what the commander asks: no lag, no delay, no acceleration limit, no
                    position term, no feed-forward (a copy of params/real_exploratory_v0.toml with those lines
                    changed, in a temporary folder).
  wall_aware_ideal  both.
  nolag             only the velocity lag removed (tau_s = 0.001); not in the record, for comparison.
  sweeps5000        the baseline with 5,000 sweeps instead of 1,000.

Prints, per variant: no-start-miss games, closest 3-D Guard-Strike distance (min, 1st and 5th percentile, median),
the share under 0.9 m and under 1.0 m. For the baseline also: of the games under 0.95 m, the share where one drone
of the closest pair is held at a wall at the deepest step, the share with a third drone within 1.3 m, games with
an emergency step, and the largest filter residual. Training simulator, exploratory drone model: not a flight
result. 3 to 10 minutes per variant at N = 300 on this laptop's CPU (the wall-aware ones are slower).
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
import time
import types
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core import safety_filter as core_sf  # noqa: E402
from svg_training.core.game import SvgGame  # noqa: E402
from svg_training.core.game_config import load_game_cfg  # noqa: E402
from svg_training.opponents.scripted import make_strategy  # noqa: E402

PARAMS = ROOT / "params" / "real_exploratory_v0.toml"
GUARDS, STRIKES = 5, 3
WALL_TOL_M = 1e-5        # a drone this close to its wall limit counts as "at the wall" for the filter
PINNED_M = 0.01          # ... and for the count of wall-pinned pairs
DEEP_M = 0.95            # games under this closest distance are the "deep" games of the pinned count
THIRD_M = 1.3            # a third drone this close to either drone of the pair counts as "nearby"

# The wall-aware filter: (old, new) text replacements in core/safety_filter.py. Each old text must occur exactly
# once, so a change to the core makes this probe fail loudly instead of silently testing something else.
# A drone at a wall gets one more projection set {v : wall_out * v <= 0 on each axis} in the Dykstra average.
WALL_PATCH = [
    ("tolerance: float = 2e-3, fixed: None = None, check_every: int = 0) -> FilterResult:",
     "tolerance: float = 2e-3, fixed: None = None, check_every: int = 0, wall_out: Tensor | None = None)"
     " -> FilterResult:"),
    ("    weight = (involvement + 1.0)[..., None]  # +1 for the speed-cap set\n",
     "    if wall_out is None:\n"
     "        wall_out = torch.zeros_like(nominal_mps)\n"
     "    pinned = (wall_out != 0).any(-1)\n"
     "    weight = (involvement + 1.0 + pinned.to(dt))[..., None]  # +1 for the speed-cap set, +1 wall set\n"),
    ("    cap_corr = torch.zeros_like(v)\n",
     "    cap_corr = torch.zeros_like(v)\n    wall_corr = torch.zeros_like(v)\n"),
    ("    w_inv, w_weight, w_same = involvement, weight, same\n",
     "    w_inv, w_weight, w_same = involvement, weight, same\n    w_wall, w_pin = wall_out, pinned\n"),
    ("            v, cap_corr, s, converged = v[live], cap_corr[live], s[live], converged[live]\n",
     "            v, cap_corr, s, converged = v[live], cap_corr[live], s[live], converged[live]\n"
     "            wall_corr, w_wall, w_pin = wall_corr[live], w_wall[live], w_pin[live]\n"),
    ("        acc = cap_proj + w_inv[..., None] * v + torch.einsum(\"npd,pm->nmd\", step, inc)\n",
     "        wy = v + wall_corr\n"
     "        wall_proj = torch.where(w_wall * wy > 0, torch.zeros_like(wy), wy)\n"
     "        acc = cap_proj + w_inv[..., None] * v + torch.einsum(\"npd,pm->nmd\", step, inc)"
     " + torch.where(w_pin[..., None], wall_proj, torch.zeros_like(wy))\n"),
    ("        res = _group_max(_drone_residual(new_v, ii, jj, member, w_g, w_bias, w_active, w_cap), w_same)\n",
     "        res = _group_max(torch.maximum(_drone_residual(new_v, ii, jj, member, w_g, w_bias, w_active, w_cap),"
     " (w_wall * new_v).clamp(min=0).amax(-1)), w_same)\n"),
    ("        cap_corr = torch.where(keep, cap_corr, capped - cap_proj)\n",
     "        cap_corr = torch.where(keep, cap_corr, capped - cap_proj)\n"
     "        wall_corr = torch.where(keep, wall_corr, wy - wall_proj)\n"),
]

# The ideal drone model: these parameter lines replaced (key -> value), everything else as committed.
IDEAL = {"kp_xy": "0.0", "tau_s": "0.001", "delay_s": "0.0", "acc_max_mps2": "inf", "ff_gain": "0.0",
         "kp_z": "0.0", "tau_z_s": "0.001"}
NOLAG = {"tau_s": "0.001"}

VARIANTS = {  # name -> (wall-aware filter, parameter changes, filter sweeps)
    "baseline": (False, {}, 1000),
    "wall_aware": (True, {}, 1000),
    "ideal_model": (False, IDEAL, 1000),
    "wall_aware_ideal": (True, IDEAL, 1000),
    "nolag": (False, NOLAG, 1000),
    "sweeps5000": (False, {}, 5000),
}


def wall_aware_filter() -> types.ModuleType:
    """The committed safety filter with WALL_PATCH applied, as a separate module (the core is untouched)."""
    src = Path(core_sf.__file__).read_text()
    for old, new in WALL_PATCH:
        n = src.count(old)
        if n != 1:
            raise RuntimeError(f"core/safety_filter.py changed: patch anchor found {n} times: {old.strip()[:60]!r}")
        src = src.replace(old, new)
    mod = types.ModuleType("safety_filter_wall_aware")
    sys.modules[mod.__name__] = mod                      # dataclasses look their module up by name
    exec(compile(src, "safety_filter_wall_aware", "exec"), mod.__dict__)
    return mod


def params_file(changes: dict[str, str], folder: Path) -> Path:
    """The committed parameter file, or a copy in `folder` with the given `key = value` lines changed."""
    if not changes:
        return PARAMS
    text = PARAMS.read_text()
    for key, val in changes.items():
        text, n = re.subn(rf"^{key}\s*=.*$", f"{key} = {val}", text, flags=re.M)
        if n != 1:
            raise RuntimeError(f"{PARAMS.name}: key {key!r} found {n} times")
    out = folder / "params_variant.toml"
    out.write_text(text)
    return out


def play(name: str, n: int, band: int, folder: Path) -> dict:
    """Play one variant; return the per-game closest distances and, for the pinned count, the logs."""
    aware, changes, iters = VARIANTS[name]
    cfg, _ = load_game_cfg(use_local=False)
    cfg = cfg.replace(**{"starling.enabled": True, "starling.filter_check_every": 8,
                         "starling.filter_iterations": iters, "starling.params": str(params_file(changes, folder))})
    game = SvgGame(cfg, n, GUARDS, STRIKES, device="cpu", seed=band, band=band)
    model = game._starling.model
    sf = wall_aware_filter() if aware else core_sf
    walls: list[torch.Tensor] = []
    res_log: list[torch.Tensor] = []
    emg_log: list[torch.Tensor] = []

    def filt(nominal: torch.Tensor, pos: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        f = model.filter_cfg
        kw = {"alpha": f["alpha"], "iterations": model.filter_iterations, "tolerance": f["tolerance"],
              **model.filter_kwargs}
        if aware:
            lo, hi = walls
            kw["wall_out"] = torch.where(pos >= hi - WALL_TOL_M, 1.0, torch.where(pos <= lo + WALL_TOL_M, -1.0, 0.0))
        r = sf.filter_velocities(nominal, pos, model.pair_mask, f["safety_radius_m"], model._filter_cap_mps, **kw)
        model.corrected = r.corrected
        res_log.append(r.residual.clone())
        emg_log.append(r.emergency.clone())
        return r.velocities, r.corrected

    model._filter = filt
    guard = make_strategy("guard_mirror", "guard", cfg, n, "cpu", 101)
    strike = make_strategy("strike_flank", "strike", cfg, n, "cpu", 202)
    obs = game.reset()
    start_miss = game.start_miss.clone().numpy()
    lim0 = (game.arenas.half_m - cfg.arena.wall_margin_m).clone().numpy()
    z_lo, z_hi = cfg.arena.height_band_m
    cc3, done_l, pos_l = [], [], []
    t0 = time.time()
    for _ in range(game.ticks):
        lim = (game.arenas.half_m - cfg.arena.wall_margin_m)[:, None, None]       # [N, 1, 1]
        walls[:] = [torch.cat((-lim, -lim, torch.full_like(lim, z_lo)), -1),
                    torch.cat((lim, lim, torch.full_like(lim, z_hi)), -1)]
        out = game.step({"guard": guard.act(obs["guard"]), "strike": strike.act(obs["strike"])})
        cc3.append(out.info["closest_cross_3d_m"].clone())
        done_l.append(out.done.clone())
        pos_l.append(model.pos_m.clone())          # after the wall stop, before a drone that is out is parked
        obs = out.obs
    secs = time.time() - t0
    cc3_a, done_a = torch.stack(cc3).numpy(), torch.stack(done_l).numpy()       # [T, N]
    steps = cc3_a.shape[0]
    first = np.where(done_a.any(0), done_a.argmax(0), steps - 1)                   # end step of each slot's game 1
    in_first = np.arange(steps)[:, None] <= first[None]
    closest = np.where(in_first, cc3_a, np.inf).min(0)
    return {"name": name, "secs": secs, "closest": closest, "start_miss": start_miss, "first": first, "lim": lim0,
            "pos": torch.stack(pos_l).numpy(), "res": torch.stack(res_log).numpy(),
            "emg": torch.stack(emg_log).numpy()}


def pinned_summary(r: dict) -> str:
    """Of the no-start-miss games under DEEP_M: closest pair at its deepest step, wall-pinned or not."""
    m = GUARDS + STRIKES
    cross = np.zeros((m, m), bool)
    cross[:GUARDS, GUARDS:] = cross[GUARDS:, :GUARDS] = True
    deep = np.where(~r["start_miss"] & (r["closest"] < DEEP_M))[0]
    if deep.size == 0:
        return f"no game without a start miss came under {DEEP_M} m"
    pinned = third = emergency = 0
    res_max = 0.0
    for gi in deep:
        f = r["first"][gi]
        p = r["pos"][: f + 1, gi]                                                   # [T, M, 3]
        d3 = np.linalg.norm(p[:, :, None] - p[:, None], axis=-1)
        dd = np.where(cross, d3, np.inf)
        k = dd.reshape(f + 1, -1).min(1).argmin()
        a, b = np.unravel_index(dd[k].argmin(), (m, m))
        margin = min((r["lim"][gi] - np.abs(p[k, i, :2])).min() for i in (a, b))
        pinned += margin < PINNED_M
        third += any(min(d3[k, a, j], d3[k, b, j]) < THIRD_M for j in range(m) if j not in (a, b))
        emergency += bool(r["emg"][: f + 1, gi].any())
        res_max = max(res_max, float(r["res"][: f + 1, gi].max()))
    nd = deep.size
    return (f"of {nd} games under {DEEP_M} m: one pair drone held at a wall at the deepest step in {pinned} "
            f"({100 * pinned / nd:.0f} %); a third drone within {THIRD_M} m in {third} ({100 * third / nd:.0f} %); "
            f"games with an emergency step {emergency}; largest filter residual {res_max:.4f}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--variants", default="baseline,wall_aware,ideal_model,wall_aware_ideal",
                    help=f"comma list from {', '.join(VARIANTS)}")
    ap.add_argument("--n", type=int, default=300, help="games at once (each slot's first game counts)")
    ap.add_argument("--band", type=int, default=0, help="arena size band: 0 lab, 1 middle, 2 large")
    ap.add_argument("--threads", type=int, default=6, help="CPU threads (the record used 6)")
    a = ap.parse_args(argv)
    names = [v.strip() for v in a.variants.split(",") if v.strip()]
    for v in names:
        if v not in VARIANTS:
            raise SystemExit(f"unknown variant {v!r}; choose from {', '.join(VARIANTS)}")
    torch.set_num_threads(a.threads)
    print(f"guard_mirror v strike_flank, 5v3, band {a.band}, N {a.n}, Starling layer, check every 8; CPU, "
          f"{a.threads} threads", flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        for v in names:
            r = play(v, a.n, a.band, Path(tmp))
            x = r["closest"][~r["start_miss"]]
            print(f"{v:17s} {r['secs']:5.0f} s  no-start-miss games {x.size}; closest 3-D min {x.min():.3f} "
                  f"p1 {np.quantile(x, .01):.3f} p5 {np.quantile(x, .05):.3f} median {np.median(x):.3f} m; "
                  f"under 0.9 m {100 * (x < 0.9).mean():.1f} %, under 1.0 m {100 * (x < 1.0).mean():.1f} %",
                  flush=True)
            if v == "baseline":
                print(f"{'':17s} {pinned_summary(r)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
