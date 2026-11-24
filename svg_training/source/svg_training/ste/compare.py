"""STE L3-L6 pipeline check, task L6.1: the numbers of the route comparison (spec
ste_learning/drafts/L3_L6_PIPELINE_SPEC.md section 3); the reading driver is ``scripts/ste_l6_read.py``.

Every read is of "these two trained policies" (one seed each), INFO; the intervals cover the sampling of the starts
only. Win indicators are the trained team's, per opponent cell, on the SAME starts (index j is one start in every
cell and in both policies); an unfinished game is no win (``scoring.pooled_row``'s rule).

* :func:`headline`: the worst cell (Wilson 95 %) among the cells that are not z_up_info, the z_up_info cells beside it.
* :func:`intervals_word`: two Wilson intervals: "above" / "below" when disjoint, else "not distinguishable".
* :func:`paired_difference`: a - b paired by start, mean with the normal 95 % interval of the per-start standard error;
  "above" / "below" when the interval excludes 0, else "not distinguishable" (a zero-width interval at 0 included).
* :func:`overall_share`: a choice share over all decisions from ``scoring.choice_share``'s bins."""
from __future__ import annotations

import math

import numpy as np

from ..core.rewards import GUARD_WIN, STRIKE_WIN
from .scoring import POOLED_Z, rate

ABOVE, BELOW, NOT_DISTINGUISHABLE = "above", "below", "not distinguishable"


def wins_by_cell(outcome, opponents: list, n: int, side: str) -> dict:
    """{opponent: bool [n]} from a batch's outcome array (cells in ``opponents``' order, n games each)."""
    outcome = np.asarray(outcome)
    if outcome.shape != (len(opponents) * n,):
        raise ValueError(f"outcome holds {outcome.shape} games, expected {len(opponents)} cells x {n}")
    won = STRIKE_WIN if side == "strike" else GUARD_WIN
    return {o: outcome[k * n:(k + 1) * n] == won for k, o in enumerate(opponents)}


def cell_rate(w) -> dict:
    w = np.asarray(w, dtype=bool)
    return {**rate(int(w.sum()), int(w.size)), "rate": float(w.mean())}


def headline(wins: dict, z_up_info) -> dict:
    """The worst cell among the cells not in ``z_up_info`` (first in cell order on a tie), the z_up_info cells
    beside it, every cell's rate."""
    z = set(z_up_info)
    cells = {o: cell_rate(w) for o, w in wins.items()}
    main = [o for o in wins if o not in z]
    if not main:
        raise ValueError("every cell is a z_up_info cell: no headline cell")
    worst = min(main, key=lambda o: cells[o]["rate"])
    return {"worst": {"opponent": worst, **cells[worst]}, "z_up_info_cells": {o: cells[o] for o in wins if o in z},
            "cells": cells,
            "note": "the interval of a minimum over K cells is optimistic (biased low, not adjusted for K)"}


def intervals_word(ci_a, ci_b) -> str:
    """a against b by two intervals: disjoint -> above / below, else not distinguishable."""
    if ci_a[0] > ci_b[1]:
        return ABOVE
    if ci_a[1] < ci_b[0]:
        return BELOW
    return NOT_DISTINGUISHABLE


def paired_difference(a, b) -> dict:
    """a - b on the same starts (per-start values: win indicators or per-start means)."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.shape != b.shape or a.ndim != 1 or a.size == 0:
        raise ValueError(f"paired values need the same starts, got {a.shape} and {b.shape}")
    d = a - b
    n = int(d.size)
    mean = float(d.mean())
    se = float(np.std(d, ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
    lo, hi = mean - POOLED_Z * se, mean + POOLED_Z * se
    word = ABOVE if lo > 0 else BELOW if hi < 0 else NOT_DISTINGUISHABLE
    return {"diff": mean, "se": se, "ci": [lo, hi], "n": n, "word": word,
            "interval": "normal, the per-start standard error of the paired difference (sample sd / sqrt(n))"}


def per_start_mean(wins: dict, members: list) -> np.ndarray:
    """y_j = the mean over ``members``' cells of the win indicator on start j (``scoring.pooled_row``'s y)."""
    return np.mean([np.asarray(wins[o], dtype=float) for o in members], axis=0)


def overall_share(entry: dict) -> dict:
    """The share of each choice over all decisions of one cell, from ``scoring.choice_share``'s per-bin shares and
    counts (None when the cell logged no decision)."""
    counts = [int(c) for c in entry["counts"]]
    total = sum(counts)
    out = {}
    for name, shares in entry["share"].items():
        if not total:
            out[name] = None
            continue
        out[name] = sum((s or 0.0) * c for s, c in zip(shares, counts)) / total
    return out
