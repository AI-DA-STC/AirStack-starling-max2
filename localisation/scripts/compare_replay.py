#!/usr/bin/env python3
"""Compare a replayed cuVSLAM path with the live one (NEAR-860).

Both are TUM files (t x y z qx qy qz qw) from the same bag's clock, in the same odometry frame, so no
alignment is done: poses are paired by timestamp (nearest, within tol_s) and the position difference is
measured directly. Coverage = paired poses / live poses.
Usage: compare_replay.py live.tum replay.tum [--json out.json] [--tol 0.01]
"""
import argparse
import json

import numpy as np


def load_tum(path):
    a = np.loadtxt(path, ndmin=2)
    return a[:, :4] if a.size else np.zeros((0, 4))


def compare(live, replay, tol_s=0.01):
    """live, replay: arrays of (t, x, y, z). Returns matched, coverage, rmse_m, max_m, final_m (None if no pair)."""
    live, replay = np.asarray(live, float), np.asarray(replay, float)
    out = {"live_n": int(len(live)), "replay_n": int(len(replay)), "matched": 0, "coverage": 0.0,
           "rmse_m": None, "max_m": None, "final_m": None, "tol_s": tol_s}
    if not len(live) or not len(replay):
        return out
    order = np.argsort(replay[:, 0]); rt = replay[order, 0]; rp = replay[order, 1:4]
    idx = np.clip(np.searchsorted(rt, live[:, 0]), 1, len(rt) - 1) if len(rt) > 1 else np.zeros(len(live), int)
    if len(rt) > 1:
        left_closer = np.abs(rt[idx - 1] - live[:, 0]) <= np.abs(rt[idx] - live[:, 0])
        idx = np.where(left_closer, idx - 1, idx)
    ok = np.abs(rt[idx] - live[:, 0]) <= tol_s
    if not ok.any():
        return out
    d = np.linalg.norm(live[ok, 1:4] - rp[idx[ok]], axis=1)
    out.update(matched=int(ok.sum()), coverage=float(ok.sum() / len(live)),
               rmse_m=float(np.sqrt(np.mean(d ** 2))), max_m=float(d.max()), final_m=float(d[-1]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("live"); ap.add_argument("replay")
    ap.add_argument("--json"); ap.add_argument("--tol", type=float, default=0.01)
    a = ap.parse_args()
    r = compare(load_tum(a.live), load_tum(a.replay), a.tol)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(r, f, indent=1)
    if r["rmse_m"] is None:
        print(f"replay vs live: no poses paired within {a.tol} s (live {r['live_n']}, replay {r['replay_n']})")
    else:
        print(f"replay vs live: coverage {100 * r['coverage']:.1f} % ({r['matched']}/{r['live_n']}), "
              f"RMSE {r['rmse_m']:.3f} m, max {r['max_m']:.3f} m, final {r['final_m']:.3f} m")


if __name__ == "__main__":
    main()
