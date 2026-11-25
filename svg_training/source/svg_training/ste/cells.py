"""Route 3, stage LS1: the cells of the reads, either team (task LS1-M1-T5; plan
ste_learning/drafts/LS1_TASK_PLAN.md, contract C6).

A read plays a team's skills, one code per drone, against every script of the other team on T44's starts:

* code index z = the index in the team's ``[players]`` list (``skills.team_skills``);
* fixed-choice cell k: every drone flies code k (a team strategy t: heads ``(t, 0)``; a drone skill d: heads
  ``(FREE, d)``), :func:`fixed_choices`;
* mixed cells: "free" combinations with at least two distinct drone skills (:func:`mixed_pool`), the read's ones
  written as data in ``configs/ste_ls1/cells.toml`` (:func:`draw_mixed` proposes them);
* every read plays ``hold_ticks = 1`` (a held ``Composite`` or changed script would freeze its command; a
  constant-heads ``SkillTeam`` is the same at any hold);
* cell player names carry a prefix (:data:`PREFIXES`) so they never shadow a script name in
  ``exploit._team_split``; each recording or stateful player is one object per cell.

The paired statistics (C7, task LS1-M1-T7; used by the calibration read LS1.5 and the equivalence read alike, so the
owner's limits are set on the gate's own ruler): :func:`paired_cell` (b, c, flips, n, the difference with Newcombe's
paired hybrid score interval, the exact sign test), :func:`adjusted_z` (Bonferroni over the side's gated cells),
:func:`pooled_difference` (the mean of the per-start means over cells, its interval at the z given), :func:`end_time`
(end-step differences), and the command-error table of M2's shape (:func:`active_rule`, the one rule M2 reuses;
:func:`command_errors`, :func:`error_summary`). Empty strata are None, never NaN (results are JSON, ``allow_nan=False``).

The players: :func:`fixed_team` (constant heads over ANY two-level dispatch: the scripts', the skill network's or a
stand-in's), :class:`Composite` (drone m flies member m closed loop, no dispatch: the oracle of a choice), and
:class:`ScriptOracle` (a stand-in for the skill network, C2, built from the scripts: exact because the scripts are
row-wise; flown through ``skills.NetTwoLevelDispatch``, it is the miniature of the distillation's positive control).

Shapes: N games, M drones of a team, K codes, B rows (drone observations), OBS_DIM observation width, COMMAND_DIM
command width. Loops run over cells, choices, codes and the M drones of a team only, never over games.
No tuned number lives here (tests/test_ste_literals.py)."""
from __future__ import annotations

import itertools
import math
import random
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
import torch
from torch import Tensor, nn

from ..core.game_config import GameCfg
from ..core.metrics import wilson_interval
from ..core.observations import OBS_DIM
from ..core.rewards import GUARD_WIN, RUNNING, STRIKE_WIN
from ..opponents.scripted import REGISTRY, make_strategy
from . import compare, exploit, skills, sweep
from .transfer import sign_test_p

SIDES = ("guard", "strike")
TEAM_KIND, FREE_KIND = "team", "free"           # a choice's kind (the run 0 ceiling's names)
# C6: the cell player names' prefixes (never a script's name)
NET_PREFIX = "net:"                             # flown by a skill network
SCR_PREFIX = "scr:"                             # flown by the scripts through the dispatch
ORC_PREFIX = "orc:"                             # an oracle (Composite, ScriptOracle)
UNF_PREFIX = "unf:"                             # an unfitted network
PERM_PREFIX = "perm:"                           # permuted codes
CAL_PREFIX = "cal:"                             # a calibration arm (changed scripts)
PREFIXES = (NET_PREFIX, SCR_PREFIX, ORC_PREFIX, UNF_PREFIX, PERM_PREFIX, CAL_PREFIX)
MIN_DISTINCT = 2                                # a mixed cell flies at least this many distinct drone skills
_ALIVE = slice(skills._V.alive, skills._V.alive + 1)   # the own-alive flag's column (C2: commands times the flag)
# C7: the interval and the correction built here (OP-11, PROPOSED until the owner confirms them with the limits)
NEWCOMBE = "newcombe_hybrid"                    # Newcombe 1998 method 10, paired hybrid score, no continuity correction
BONFERRONI = "bonferroni_per_side"              # adjusted_z(alpha, m), m the side's gated cells
DEGENERATE = "phi = 0: a zero margin total (degenerate cell)"
END_TIME_PCT = 90                               # end_time's upper percentile of |end-step difference|


@dataclass(frozen=True)
class CellSpec:
    """What the cells of one team need from a gate file: ``side``; ``players`` (the team's ``[players]`` list: code
    order); the two-level lists ``team_strategies`` and ``drone_skills``; ``drones`` (M, the team's size)."""
    side: str
    players: tuple[str, ...]
    team_strategies: tuple
    drone_skills: tuple
    drones: int


def other(side: str) -> str:
    """The other team."""
    if side not in SIDES:
        raise ValueError(f"side must be one of {SIDES}, got {side!r}")
    return SIDES[1 - SIDES.index(side)]


def cell_of(side: str, mine: str, opp: str) -> tuple[str, str]:
    """The cell (Guard, Strike) where ``side`` plays ``mine`` against ``opp``."""
    return (mine, opp) if side == SIDES[0] else (opp, mine)


def cell_spec(gates, side: str) -> CellSpec:
    """The ``CellSpec`` of ``side`` from a loaded gate file (``exploit.ExploitGates``) of the two-level skills route;
    ValueError for any other route."""
    other(side)
    spec = gates.learner
    if not (spec.skills and spec.choice == skills.TWO_LEVEL):
        raise ValueError(f"the cells need a two-level skills gate file ([learner] choice = \"{skills.TWO_LEVEL}\"), "
                         f"got action {spec.action!r}, choice {spec.choice!r}")
    guards, strikes = sweep.parse_size(gates.run["size"])
    return CellSpec(side, tuple(skills.team_skills(gates.players, side)), tuple(spec.team_strategies[side]),
                    tuple(spec.drone_skills[side]), int(guards if side == SIDES[0] else strikes))


def _choice(spec: CellSpec, flies: list[str]) -> dict:
    """A "free" choice flying ``flies`` (one drone skill per slot)."""
    return {"name": FREE_KIND + ":" + "+".join(flies), "kind": FREE_KIND,
            "heads": [(skills.FREE, spec.drone_skills.index(s)) for s in flies], "flies": list(flies),
            "script": flies[0] if len(set(flies)) == 1 else None}


def _team_choice(spec: CellSpec, t: int, name: str) -> dict:
    return {"name": f"{TEAM_KIND}:{name}", "kind": TEAM_KIND, "heads": [(t, 0)] * spec.drones,
            "flies": [name] * spec.drones, "script": name}


def all_choices(spec: CellSpec) -> list[dict]:
    """Every constant choice of the team, in the run 0 ceiling's order (``scripts/ste_l3_run0_ceiling.choices``, either
    team): the team strategies (team head t >= 1, drone head 0), then under "free" every per-slot combination of the
    drone skills (slot 0 the slowest-changing digit). Each: name, kind, heads [(t, d)] per slot, flies [player per
    slot], script (the one script every drone flies, or None)."""
    out = [_team_choice(spec, t, s) for t, s in enumerate(spec.team_strategies, start=1)]
    for combo in itertools.product(range(len(spec.drone_skills)), repeat=spec.drones):
        out.append(_choice(spec, [spec.drone_skills[d] for d in combo]))
    return out


def fixed_choices(spec: CellSpec) -> list[dict]:
    """The fixed-choice cells (C6), one per code in ``players`` order: every drone flies code k (a team strategy as
    the team head, a drone skill under "free" on every drone)."""
    out = []
    for name in spec.players:
        if name in spec.team_strategies:
            out.append(_team_choice(spec, spec.team_strategies.index(name) + 1, name))
        else:
            out.append(_choice(spec, [name] * spec.drones))
    return out


def mixed_pool(spec: CellSpec) -> list[tuple[str, ...]]:
    """Every "free" combination of the drone skills (one per slot, ``itertools.product`` order) with at least
    ``MIN_DISTINCT`` distinct skills: 24 for a 3-drone team of 3 drone skills, 60 for 4."""
    return [c for c in itertools.product(spec.drone_skills, repeat=spec.drones) if len(set(c)) >= MIN_DISTINCT]


def mixed_choices(spec: CellSpec, combos) -> list[dict]:
    """The choices of the mixed combinations ``combos`` (each a member of :func:`mixed_pool`; ValueError otherwise)."""
    pool = set(mixed_pool(spec))
    bad = [tuple(c) for c in combos if tuple(c) not in pool]
    if bad:
        raise ValueError(f"not mixed combinations of the {spec.side} team's drone skills: {bad}")
    return [_choice(spec, list(c)) for c in combos]


def draw_mixed(spec: CellSpec, count: int, seed: int) -> list[tuple[str, ...]]:
    """``count`` distinct members of :func:`mixed_pool`, drawn by the standard library's ``random.Random(seed)``
    (stable across torch and NumPy versions). A proposal tool: the read's combinations are written as data in
    ``configs/ste_ls1/cells.toml``, so no read relies on this stream."""
    return random.Random(seed).sample(mixed_pool(spec), count)


class ConstHeads(nn.Module):
    """A constant two-level network (copy of ``scripts/ste_l3_run0_ceiling.ConstHeads``): logits [B, T + 1 + K_d] with
    1 at team index ``t`` and at drone index ``d``, 0 elsewhere, whatever the observation [B, D]."""

    def __init__(self, t: int, d: int, widths: tuple[int, int]):
        super().__init__()
        self.t, self.d, self.widths = int(t), int(d), tuple(widths)

    def forward(self, obs: Tensor) -> Tensor:
        out = obs.new_zeros(obs.shape[0], sum(self.widths))
        out[:, self.t] = 1.0
        out[:, self.widths[0] + self.d] = 1.0
        return out


def fixed_team(spec: CellSpec, choice: dict, dispatch: skills.TwoLevelDispatch, name: str) -> exploit.SkillTeam:
    """The ``SkillTeam`` of ``spec.side`` that plays ``choice`` every decision through ``dispatch`` (any two-level
    dispatch of the team: the scripts', a skill network's, a stand-in's): a constant network per drone slot, identity
    scalers, named ``name`` (give each cell its own name and dispatch: C6)."""
    nets = [ConstHeads(t, d, dispatch.widths) for t, d in choice["heads"]]
    return exploit.SkillTeam(spec.side, nets, [lambda o, train=False: o] * len(nets), dispatch, name=name)


def _member_team(member) -> str | None:
    """The team a member plays: a script name's class TEAM (None for either), a player object's ``team``."""
    if isinstance(member, str):
        return getattr(REGISTRY.get(member), "TEAM", None)
    return member.team


class Composite:
    """The oracle of a choice, written without the dispatch: drone m flies member m closed loop (column m of that
    member's command on the whole team's observation [N, M, D] -> [N, M, 4]). A member is a script name
    (``make_strategy``) or a player object (``team``, ``reset``, ``act``); every member must play ``side``
    (ValueError). ``name`` (default ``ORC_PREFIX`` + the members joined by "+")."""

    def __init__(self, side: str, members: list, cfg: GameCfg, n: int, device: str = "cpu", seed: int = 0,
                 name: str | None = None):
        other(side)
        wrong = [m if isinstance(m, str) else getattr(m, "name", repr(m)) for m in members
                 if _member_team(m) not in (None, side)]
        if wrong:
            raise ValueError(f"a {side} Composite cannot fly the other team's players {wrong}")
        self.members = [make_strategy(m, side, cfg, n, device, seed) if isinstance(m, str) else m for m in members]
        labels = [m if isinstance(m, str) else m.name for m in members]
        self.team, self.name = side, name if name is not None else ORC_PREFIX + "+".join(labels)

    def reset(self, games: Tensor) -> None:
        for m in self.members:
            m.reset(games)

    def act(self, obs: Tensor) -> Tensor:
        if obs.shape[1] != len(self.members):
            raise ValueError(f"team size: {self.name} has {len(self.members)} members, the observation "
                             f"{obs.shape[1]} drones")
        return torch.stack([m.act(obs)[:, i] for i, m in enumerate(self.members)], dim=1)


class ScriptOracle(nn.Module):
    """A stand-in for a team's skill network (C2: the same call, attributes and alive rule), built from the scripts:
    ``forward(obs [B, OBS_DIM], slot [B] long, z [B] long) -> [B, COMMAND_DIM]`` puts each row at index ``slot`` of a
    zero team tensor [B, M, OBS_DIM], runs each of the K scripts once on it and gathers row b's command at
    ``[b, slot_b, z_b]``, times the row's alive flag. Exact (``torch.equal`` to the scripts' team commands) because
    the scripts are row-wise: a drone's command reads its own observation row only (tests/test_ste_ls1_cells.py
    ``test_the_scripts_are_row_wise``). Attributes ``team``, ``skills`` (tuple), ``k``, ``team_size``.
    ``n_rows_hint``: the scripts' ``num_games`` (none of the skills reads it; default 1)."""

    def __init__(self, cfg: GameCfg, side: str, skills: list[str], team_size: int, n_rows_hint: int | None = None):
        super().__init__()
        other(side)
        if not skills:
            raise ValueError("skills: at least one skill")
        self.team, self.skills, self.k, self.team_size = side, tuple(skills), len(skills), int(team_size)
        rows = int(n_rows_hint) if n_rows_hint is not None else 1
        self.scripts = [make_strategy(s, side, cfg, rows, "cpu", 0) for s in self.skills]

    def forward(self, obs: Tensor, slot: Tensor, z: Tensor, clip: bool = True) -> Tensor:
        b = obs.shape[0]
        row = torch.arange(b, device=obs.device)
        team = obs.new_zeros(b, self.team_size, OBS_DIM)
        team[row, slot] = obs
        every = torch.stack([s.act(team)[row, slot] for s in self.scripts], dim=1)      # [B, K, COMMAND_DIM]
        out = every[row, z]
        if clip:
            out = out.clamp(-1, 1)
        return out * obs[:, _ALIVE]


# ================================================================================================ C7: the paired statistics
def _side_wins(outcome, side: str) -> np.ndarray:
    """The win indicator of ``side`` per game; ValueError on an unfinished game (as ``scoring.paired_wins``)."""
    outcome = np.asarray(outcome)
    if (outcome == RUNNING).any():
        raise ValueError("a game did not finish: paired counts need finished games")
    other(side)
    return outcome == (GUARD_WIN if side == SIDES[0] else STRIKE_WIN)


def newcombe_phi(both: int, b: int, c: int, neither: int) -> float:
    """The phi coefficient of the paired 2 x 2 table (``both`` won by both, ``b`` by the reference only, ``c`` by the arm
    only, ``neither``): (both x neither - b x c) / sqrt of the product of the four margin totals; 0 when one is zero."""
    denom = (both + b) * (c + neither) * (both + c) * (b + neither)
    return (both * neither - b * c) / math.sqrt(denom) if denom > 0 else 0.0


def newcombe_interval(both: int, b: int, c: int, neither: int, z: float) -> tuple[list[float], bool]:
    """Newcombe's paired hybrid score interval (1998, method 10, no continuity correction) of the arm's win share less
    the reference's, (c - b) / n: the Wilson intervals at ``z`` of the two shares (l_a, u_a) and (l_r, u_r), and
    lower = d - sqrt((p_a - l_a)^2 - 2 phi (p_a - l_a)(u_r - p_r) + (u_r - p_r)^2),
    upper = d + sqrt((u_a - p_a)^2 - 2 phi (u_a - p_a)(p_r - l_r) + (p_r - l_r)^2).
    Returns ([lower, upper], degenerate) (degenerate: phi set to 0, a zero margin total)."""
    n = both + b + c + neither
    p_a, p_r = (both + c) / n, (both + b) / n
    l_a, u_a = wilson_interval(both + c, n, z)
    l_r, u_r = wilson_interval(both + b, n, z)
    phi = newcombe_phi(both, b, c, neither)
    degenerate = (both + b) * (c + neither) * (both + c) * (b + neither) == 0
    d = p_a - p_r
    lo = d - math.sqrt(max(0.0, (p_a - l_a) ** 2 - 2 * phi * (p_a - l_a) * (u_r - p_r) + (u_r - p_r) ** 2))
    hi = d + math.sqrt(max(0.0, (u_a - p_a) ** 2 - 2 * phi * (u_a - p_a) * (p_r - l_r) + (p_r - l_r) ** 2))
    return [lo, hi], degenerate


def paired_cell(arm_pg: dict, ref_pg: dict, side: str, z: float) -> dict:
    """One cell, paired by start (the same starts, game for game): ``b`` games the arm lost that the reference won,
    ``c`` the reverse, ``flips`` = b + c, ``n``, ``diff`` = (c - b) / n (the arm's win share less the reference's) with
    ``ci`` (:func:`newcombe_interval` at ``z``), ``sign_test_p`` (exact two-sided, ``transfer.sign_test_p``) and
    ``method``. Wins of ``side`` (holds for the Guard team, reaches for the Strike team); every game must be finished
    (ValueError). n = 0: diff, ci and sign_test_p None."""
    arm, ref = _side_wins(arm_pg["outcome"], side), _side_wins(ref_pg["outcome"], side)
    if arm.shape != ref.shape:
        raise ValueError(f"paired games differ in number: {arm.shape} v {ref.shape}")
    n = int(arm.size)
    both, neither = int((arm & ref).sum()), int((~arm & ~ref).sum())
    b, c = int((ref & ~arm).sum()), int((arm & ~ref).sum())
    if n == 0:
        return {"b": 0, "c": 0, "flips": 0, "n": 0, "diff": None, "ci": None, "sign_test_p": None, "method": NEWCOMBE}
    ci, degenerate = newcombe_interval(both, b, c, neither, z)
    return {"b": b, "c": c, "flips": b + c, "n": n, "diff": (c - b) / n, "ci": ci, "sign_test_p": sign_test_p(b, c),
            "method": NEWCOMBE + (f" ({DEGENERATE})" if degenerate else "")}


def adjusted_z(alpha: float, m: int) -> float:
    """The two-sided normal quantile at alpha / m (Bonferroni over ``m`` cells): NormalDist().inv_cdf(1 - alpha / (2 m)).
    m = 1: the plain z (1.959964 at alpha 0.05)."""
    alpha = float(alpha)
    if not (0 < alpha < 1) or int(m) != m or m < 1:
        raise ValueError(f"adjusted_z needs 0 < alpha < 1 and a whole m >= 1, got alpha {alpha!r}, m {m!r}")
    return NormalDist().inv_cdf(1 - alpha / (2 * int(m)))


def pooled_difference(arm_wins: dict, ref_wins: dict, z: float) -> dict | None:
    """The pooled difference over cells: ``arm_wins`` and ``ref_wins`` {cell: win indicator [n]} on the same n starts
    (the same keys); the difference of the per-start means over cells (``compare.per_start_mean``, the y of
    ``scoring.pooled_row``), its standard error by ``compare.paired_difference`` and the interval recomputed at ``z``
    (``compare`` and ``scoring`` hard-wire 1.96: their ci is never used). None for no cell; se and ci None for one
    start. Returns {"diff", "se", "ci", "cells", "n"}."""
    if set(arm_wins) != set(ref_wins):
        raise ValueError(f"the pooled difference needs the same cells, got {sorted(arm_wins)} and {sorted(ref_wins)}")
    members = list(arm_wins)
    if not members:
        return None
    r = compare.paired_difference(compare.per_start_mean(arm_wins, members), compare.per_start_mean(ref_wins, members))
    se = r["se"] if math.isfinite(r["se"]) else None
    ci = [r["diff"] - z * se, r["diff"] + z * se] if se is not None else None
    return {"diff": r["diff"], "se": se, "ci": ci, "cells": len(members), "n": r["n"]}


def end_time(arm_pg: dict, ref_pg: dict) -> dict:
    """End-step differences, arm less reference, over the cell's n paired games (ticks): ``differ_games`` (games that
    ended on another tick), the mean, the median, the mean of |d| and its ``END_TIME_PCT``-th percentile. n = 0: None."""
    d = np.asarray(arm_pg["end_step"], dtype=np.int64) - np.asarray(ref_pg["end_step"], dtype=np.int64)
    if d.size == 0:
        return {"differ_games": 0, "mean_ticks": None, "median_ticks": None, "mean_abs_ticks": None,
                "p90_abs_ticks": None}
    return {"differ_games": int((d != 0).sum()), "mean_ticks": float(d.mean()), "median_ticks": float(np.median(d)),
            "mean_abs_ticks": float(np.abs(d).mean()), "p90_abs_ticks": float(np.percentile(np.abs(d), END_TIME_PCT))}


# ------------------------------------------------------------------------------------------------ the command error
def active_rule(label_max_abs) -> list[bool]:
    """M2-T3's rule, one function for the calibration and the distillation: per channel, active where any script label
    on that channel is not 0.0 on the same rows, i.e. where the largest |label| is above 0."""
    return [bool(float(v) > 0) for v in label_max_abs]


def command_errors(acc: dict) -> dict:
    """The command-error table of M2's shape from per-skill accumulators ``acc`` {skill: {"sum_sq" [4], "max_abs" [4],
    "count" (rows), "label_max_abs" [4] (the scripts' own labels on the same rows)}}: {"skills": {skill: {"rmse" [4]
    or None, "max_abs" [4] or None, "active" [4] (:func:`active_rule`), "rows"}}, "zero_skill"} (the first skill, in
    ``acc`` order, with rows and every label exactly 0; None if none)."""
    skills_out, zero = {}, None
    for name, a in acc.items():
        rows = int(a["count"])
        active = active_rule(a["label_max_abs"]) if rows else [False] * len(a["label_max_abs"])
        skills_out[name] = {"rmse": [math.sqrt(float(s) / rows) for s in a["sum_sq"]] if rows else None,
                            "max_abs": [float(v) for v in a["max_abs"]] if rows else None,
                            "active": active, "rows": rows}
        if rows and not any(active) and zero is None:
            zero = name
    return {"skills": skills_out, "zero_skill": zero}


def error_summary(errors: dict) -> dict:
    """The three numbers the command-error limits read (C7): ``rmse_active_max`` (the largest RMSE on an active channel
    of any skill), ``unused_max_abs`` (the largest |error| on a channel a skill never uses, the zero-command skill
    excluded) and ``zero_skill_max_abs`` (the zero-command skill's largest |error|); None where nothing was seen."""
    rmse, unused, zero = [], [], None
    for name, s in errors["skills"].items():
        if not s["rows"]:
            continue
        if name == errors["zero_skill"]:
            zero = max(s["max_abs"])
            continue
        rmse += [r for r, act in zip(s["rmse"], s["active"]) if act]
        unused += [m for m, act in zip(s["max_abs"], s["active"]) if not act]
    return {"rmse_active_max": max(rmse) if rmse else None, "unused_max_abs": max(unused) if unused else None,
            "zero_skill_max_abs": zero}
