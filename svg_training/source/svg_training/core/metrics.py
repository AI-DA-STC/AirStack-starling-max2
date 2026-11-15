"""S2 match metrics: hold rate, Wilson 95 % interval and per-band summary rows (S2 Task 6).

One metrics module serves scoring, evaluation and records (STANDARDS §7 rule 2). These functions run AFTER a
match, outside the game step: ``summarise`` moves the result to the host once."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import torch
from torch import Tensor

from .arena import BANDS
from .rewards import GUARD_WIN, RUNNING

if TYPE_CHECKING:     # play.py imports this module; the type is only needed for hints
    from .play import MatchResult

QUANTILES = (0.05, 0.25, 0.50)      # closest opposite approach: reported beside its minimum


def hold_rate(outcome: Tensor) -> float:
    """outcome [N] int8 (0 running, 1 Strike win, 2 Guard win) -> share of FINISHED games the Guard team held
    (Guard win). NaN if no game finished."""
    finished = outcome != RUNNING
    n = int(finished.sum())
    return float((outcome == GUARD_WIN).sum()) / n if n else float("nan")


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for k successes in n trials (z = 1.96: 95 %). Returns (low, high) in [0, 1];
    (nan, nan) if n = 0."""
    if n <= 0:
        return float("nan"), float("nan")
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def _finite_or_none(v: float) -> float | None:
    return v if math.isfinite(v) else None


def _row(res: "dict[str, Tensor]", sel: Tensor) -> dict:
    """Summary of the finished games selected by sel [N] bool (host tensors)."""
    fin = sel & (res["outcome"] != RUNNING)
    n = int(fin.sum())
    k = int((res["outcome"][fin] == GUARD_WIN).sum())
    lo, hi = wilson_interval(k, n)
    cc = res["closest_cross_m"][fin]
    cc = cc[torch.isfinite(cc)].double()
    row = {"games": n, "guard_wins": k, "hold_rate": k / n if n else None, "ci_low": lo if n else None,
           "ci_high": hi if n else None,
           "mean_end_step": float(res["end_step"][fin].double().mean()) if n else None,
           "closest_cross_m": float(cc.min()) if cc.numel() else None}
    for q in QUANTILES:
        row[f"closest_cross_p{round(q * 100):02d}_m"] = float(torch.quantile(cc, q)) if cc.numel() else None
    row["rule_breach_rate"] = float(res["rule_breach"][fin].double().mean()) if n else None
    row["filter_rate"] = float(res["filter_corrected_rate"][fin].double().mean()) if n else None
    row["start_miss_rate"] = float(res["start_miss"][fin].double().mean()) if n else None
    return {k2: (_finite_or_none(v) if isinstance(v, float) else v) for k2, v in row.items()}


def summarise(res: "MatchResult", by: tuple[str, ...] = ("band",)) -> list[dict]:
    """Rows of finished first games, grouped by the keys in ``by`` (any of "band", "start_miss"; () = one row).

    Each row: the group keys ("band" as its name in BANDS), games, guard_wins, hold_rate, ci_low, ci_high
    (Wilson 95 %), mean_end_step, closest_cross_m (the minimum over the games: the closest any opposite pair
    came, horizontal, m) and its 5th, 25th and 50th percentiles over games (closest_cross_p05_m, _p25_m, _p50_m;
    games with no live opposite pair are left out), rule_breach_rate (share of games with at least one step where
    an opposite pair was closer than the keep-out), filter_rate (mean over games of the share of live drone-steps
    the safety filter changed; 0 without the Starling layer), start_miss_rate (share of games whose starts could
    not meet the spacing / keep-out). A value that cannot be computed is None; a group with no finished game
    gives no row (so no finished game at all gives []). Moves the result to the host once.
    """
    for key in by:
        if key not in ("band", "start_miss"):
            raise ValueError(f"cannot group by {key!r}: use 'band' and/or 'start_miss'")
    h = {name: getattr(res, name).detach().cpu() for name in
         ("outcome", "end_step", "band", "closest_cross_m", "rule_breach", "filter_corrected_rate", "start_miss")}
    groups: list[tuple[dict, Tensor]] = [({}, h["outcome"] != RUNNING)]      # finished first games only
    for key in by:
        values = range(len(BANDS)) if key == "band" else (False, True)
        nxt = []
        for keys, sel in groups:
            for v in values:
                s = sel & (h[key] == v)
                if bool(s.any()):
                    nxt.append(({**keys, key: BANDS[v] if key == "band" else bool(v)}, s))
        groups = nxt
    return [{**keys, **_row(h, sel)} for keys, sel in groups if bool(sel.any())]
