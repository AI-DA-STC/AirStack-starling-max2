"""Every stage 5.2 number (NUS port Phase 5, Tasks S4 and S5; STANDARDS section 7.2: one module serves the training curves, the
evaluation, the gates and the record). The trainer (``scripts/nus_tier1_train.py``) and the evaluation runner (``scripts/nus_phase5_eval.py``)
compute nothing themselves.

* :func:`rate` - a rate ``k/n`` with its Wilson 95 % interval (``core.metrics.wilson_interval``, the interval of every Phase 4 record).
* :func:`training_row` - one update's training-curve row: the learner's metrics (entropy, KL, clip fraction, value loss, ...), the win rate
  per pool slot, and from the environment's counters (``NusTier1Env.counters``) the Strike reach rate, the safety filter's intervention
  share and mean correction size, the smoothness (change of the command between decisions), the same-team closest approach in 3-D, the
  non-finite actions and states, and the clamp share.
* :func:`reference_bars` - the pre-registered bars of ``[gates.phase5_tier1_training]`` from Phase 4 row 5's ``scores.json``: for each
  Strike of ``guard_strikes`` the highest Wilson upper bound of the hold rate (1 - reach) of any row 5 Guard scored against it (G-1 to
  G-4), and for each Guard of ``strike_guards`` the Wilson upper bound of S20's reach rate against it (S-1).
* :func:`seed_verdict`, :func:`stage_verdict` - a seed passes when every Guard gate, the Strike gate and the non-finite gate pass (F-1 holds
  by construction); the stage PASSES when at least ``min_seeds_passing`` seeds pass and the control C-1 holds; a C-1 failure stops before
  any verdict.
* :func:`control_differences` - C-1: games whose outcome differs from the reference outcomes, game by game.

No numeric literal other than 0, 1, -1, 2 (G2); rates are plain floats, intervals at the records' 95 %.
"""
from __future__ import annotations

import inspect
import math
from statistics import NormalDist
from typing import Any

import torch
from torch import Tensor

from ..core.metrics import wilson_interval

GUARD_GATES = ("G-1", "G-2", "G-3", "G-4")
STRIKE_GATES = ("S-1",)
_Z = inspect.signature(wilson_interval).parameters["z"].default          # the records' Wilson z
CONFIDENCE_BUILT = round(2 * NormalDist().cdf(_Z) - 1, 2)                # its two-sided confidence, to the gate table's two digits
REFERENCE_STRIKE = "S20"  # S-1: S20's reach against the same Guard on row 5


def rate(k: int, n: int) -> dict[str, Any]:
    """{"k", "n", "rate", "ci_low", "ci_high"} (Wilson 95 %); rate and bounds None when n = 0."""
    k, n = int(k), int(n)
    low, high = wilson_interval(k, n)
    return {"k": k, "n": n, "rate": k / n if n else None, "ci_low": low if n else None, "ci_high": high if n else None}


def hold_of(reach: dict[str, Any]) -> dict[str, Any]:
    """The hold rate (1 - reach) of a reach rate dict, with its own Wilson interval."""
    return rate(reach["n"] - reach["k"], reach["n"])


# ------------------------------------------------------------------------------------------------ training curves (S4)
def training_row(update: dict[str, float], counters: dict[str, Tensor], team: str) -> dict[str, Any]:
    """One update's row (host floats; one read of the counters). ``update``: ``SelfPlay._update``'s metrics; ``counters``: the
    environment's per-game counters of the update's games (``NusTier1Env.counters``); ``team``: the learner's team."""
    c = {k: v.detach().cpu() for k, v in counters.items()}
    games = int(c["reached"].numel())
    live = float(c["live_ticks"].sum())
    corrected = float(c["corrected_ticks"].sum())
    team_min = c["team_min_3d_m"][torch.isfinite(c["team_min_3d_m"])].double()
    row: dict[str, Any] = {"team": team, "games": games, **{k: float(v) for k, v in update.items()}}
    row["strike_reach"] = rate(int(c["reached"].sum()), games)
    row["filter_share"] = corrected / live if live else None
    row["correction_size_mps"] = float(c["correction_sum_mps"].sum()) / corrected if corrected else None
    smooth_n = float(c["smooth_n"].sum())
    row["smoothness_decision_mps"] = float(c["smooth_sum_mps"].sum()) / smooth_n if smooth_n else None
    row["team_min_3d_m"] = {"min": float(team_min.min()), "p50": float(team_min.median())} if team_min.numel() else None
    row["nonfinite_actions"] = int(c["nonfinite_actions"].sum())
    if "clamp_ticks" in c:
        live_clamp = int(c["live_ticks_clamp"].sum())
        row["clamp_share"] = int(c["clamp_ticks"].sum()) / live_clamp if live_clamp else None
        row["nonfinite_states"] = int(c["nonfinite_state"].sum())
    bad = [k for k, v in row.items() if isinstance(v, float) and not math.isfinite(v)]
    row["nonfinite_metrics"] = bad
    return row


# ------------------------------------------------------------------------------------------------ bars and verdicts (S5)
def check_confidence(confidence: float) -> None:
    if round(float(confidence), 2) != CONFIDENCE_BUILT:
        raise ValueError(f"only Wilson {CONFIDENCE_BUILT} intervals are built (the records' z); the gate table asks for {confidence}")


def reference_bars(scores: dict[str, Any], guard_strikes: list[str], strike_guards: list[str]) -> dict[str, dict[str, Any]]:
    """The bars from a row's ``scores.json`` (``{"pairs": [{"guard", "strike", "reach": {"k", "n"}}]}``): gate id -> {"against",
    "bar", "from"}. Refuses a Strike no row Guard was scored against, or a Guard with no S20 pair."""
    pairs = scores["pairs"]
    if len(guard_strikes) != len(GUARD_GATES) or len(strike_guards) != len(STRIKE_GATES):
        raise ValueError("the gate table's Strike and Guard lists do not match the gates G-1 to G-4 and S-1")
    bars: dict[str, dict[str, Any]] = {}
    for gate, strike in zip(GUARD_GATES, guard_strikes):
        found = [p for p in pairs if p["strike"] == strike]
        if not found:
            raise ValueError(f"{gate}: no reference Guard was scored against {strike!r}")
        uppers = [(hold_of(p["reach"])["ci_high"], p["guard"]) for p in found]
        top = max(u for u, _ in uppers)
        bars[gate] = {"team": "guard", "against": strike, "bar": top, "from": sorted(g for u, g in uppers if u == top)}
    for gate, guard in zip(STRIKE_GATES, strike_guards):
        found = [p for p in pairs if p["guard"] == guard and p["strike"] == REFERENCE_STRIKE]
        if not found:
            raise ValueError(f"{gate}: no reference pair {guard} v {REFERENCE_STRIKE}")
        bars[gate] = {"team": "strike", "against": guard, "bar": rate(found[0]["reach"]["k"], found[0]["reach"]["n"])["ci_high"],
                      "from": [REFERENCE_STRIKE]}
    return bars


def seed_verdict(results: dict[str, dict[str, Any]], bars: dict[str, dict[str, Any]], nonfinite_max: int) -> dict[str, Any]:
    """One seed: ``results`` gate id -> {"reach": rate dict, "nonfinite": int} of our checkpoint's pairing. A Guard gate passes when
    the Wilson lower bound of our hold rate is above its bar, the Strike gate when the lower bound of our reach rate is; F-2 when the
    non-finite count over every pairing is at most ``nonfinite_max``."""
    gates: dict[str, Any] = {}
    for gate, bar in bars.items():
        r = results[gate]["reach"]
        ours = hold_of(r) if bar["team"] == "guard" else rate(r["k"], r["n"])
        gates[gate] = {"ours": ours, "bar": bar["bar"], "pass": ours["ci_low"] is not None and ours["ci_low"] > bar["bar"]}
    nonfinite = sum(int(r["nonfinite"]) for r in results.values())
    gates["F-2"] = {"nonfinite": nonfinite, "pass": nonfinite <= nonfinite_max}
    gates["F-1"] = {"pass": True, "note": "met by construction (the game clamps every drone into the keep-in box after each step)"}
    return {"gates": gates, "pass": all(g["pass"] for g in gates.values())}


def stage_verdict(seeds: dict[str, dict[str, Any]], control_games_differ: int | None, min_seeds_passing: int) -> dict[str, Any]:
    """The stage: a C-1 failure (any game differing, or the control not run) stops before any verdict; otherwise PASS when at least
    ``min_seeds_passing`` seeds pass, else FAIL. The claim is worded by the count."""
    if control_games_differ is None or control_games_differ != 0:
        return {"verdict": "STOPPED", "reason": "control C-1 did not hold (train-debug before any verdict)", "control_games_differ":
                control_games_differ}
    passing = sorted(s for s, v in seeds.items() if v["pass"])
    total = len(seeds)
    claim = f"in all {total} seeds" if len(passing) == total else f"in {len(passing)} of {total} seeds"
    verdict = "PASS" if len(passing) >= min_seeds_passing else "FAIL"
    return {"verdict": verdict, "seeds_passing": passing, "seeds": total, "claim": claim, "control_games_differ": 0}


def control_differences(outcome: Tensor, reference: Tensor) -> int:
    """C-1: games whose outcome differs, game by game (both [N])."""
    if outcome.shape != reference.shape:
        raise ValueError("the control and its reference hold different game counts")
    return int((outcome.to(torch.long) != reference.to(torch.long)).sum())


def clamp_share(clamp_ticks: Tensor, live_ticks: Tensor) -> dict[str, Any]:
    """INFO beside F-1: clamped live drone-ticks over live drone-ticks, summed over games."""
    return rate(int(clamp_ticks.sum()), int(live_ticks.sum()))
