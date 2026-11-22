"""STE learning track: the scoring parts shared by the drivers that score saved players on the reference starts
(``scripts/ste_exploit_l012.py``, ``scripts/ste_cross_tag_l012d.py``, ``scripts/ste_score_matrix.py``). Factored out of
the first two for the L1 side track (spec ``ste_learning/drafts/L1_SIDE_TRACK_SPEC.md`` v2, item 5); their behaviour is
unchanged (the scripts re-export these names).

Per-game arrays (``pg``) are the host arrays of ``exploit.play_cells``: cells x n games, Guard drones first. Wins are the
trained side's: holds for the Guard team, reaches for the Strike team. Standard library, NumPy and PyTorch only; no tuned
number lives here (tests/test_ste_literals.py)."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import torch
from torch import Tensor

from ..core.game_config import TICK_S
from ..core.metrics import wilson_interval
from ..core.observations import ObsView
from ..core.rewards import GUARD_WIN, RUNNING, STRIKE_WIN
from . import exploit, sweep
from .run_contract import EXIT_CONTROL_FAILED, EXIT_NONFINITE
from .transfer import paired as transfer_paired

PASS, FAIL, NONFINITE = "PASS", "FAIL", "NONFINITE"
EXACT_RULE = "cpu"          # exploit.replay_ok's game-for-game branch, applied on any device ("game for game")
SHA_SHOWN = 12              # hex digits of a sha256 shown in a control's detail
END_REASONS = ("reach", "all_strikes_tagged", "clock", "other_hold", "unfinished")
TIME_LEFT_KEYS = ("offset_s", "clamp_max_s")   # [player] time_left: exactly one (L1.14, spec addendum 2)
GAMES_SHOWN = 12            # game indices shown per kind of mismatch in a control's record
WHOLE_TICK_TOL = 1e-6       # an offset must be a whole number of ticks within this many ticks (90 s / 0.05 s = 1800)


def win_count(pg: dict, side: str) -> tuple[int, int]:
    """(wins of ``side``, finished games) of one cell."""
    c = exploit.counts(pg)
    return (c["reaches"] if side == "strike" else c["holds"]), c["games"]


def rate(k: int, n: int) -> dict:
    """k of n with its Wilson 95 % interval."""
    lo, hi = wilson_interval(k, n)
    return {"k": int(k), "n": int(n), "ci": [lo, hi]}


def plumbing_controls(pg: dict, ref, n: int, phase: str, suffix: str = "") -> dict:
    """Paired starts, one for one, no non-finite action, on one evaluation batch (gate [controls]; QC I-6: on every
    batch). A non-finite action is status NONFINITE (the run contract's exit 5), not FAIL."""
    out = {}
    shas = {s for s in pg["start_sha256"]}
    want = exploit.starts_sha(ref.starts_m[:n])
    out[f"ctl_paired_starts{suffix}"] = {"status": PASS if shas == {want} else FAIL, "phase": phase,
                                         "detail": f"{len(shas)} start set(s), reference {want[:SHA_SHOWN]}"}
    bad = int(np.sum((pg["guards_removed"] != pg["tags"]) | (pg["guards_tagged"] != pg["tags"])))
    out[f"tags_one_for_one{suffix}"] = {"status": PASS if bad == 0 else FAIL, "phase": phase,
                                        "detail": f"{bad} games not one for one of {len(pg['tags'])}"}
    nf = int(pg["nonfinite_actions"].sum())
    out[f"no_nonfinite_actions{suffix}"] = {"status": PASS if nf == 0 else NONFINITE, "phase": phase,
                                            "detail": f"{nf} non-finite actions"}
    return out


def ending(controls: dict) -> int | None:
    """The exit a control record calls for: NONFINITE -> 5 (run contract), FAIL -> 6, else None."""
    statuses = {v["status"] for v in controls.values()}
    return EXIT_NONFINITE if NONFINITE in statuses else EXIT_CONTROL_FAILED if FAIL in statuses else None


def control_status(parts: dict, ok: bool) -> str:
    """NONFINITE if any part is; PASS if ``ok`` and every part PASS; else FAIL."""
    statuses = {v["status"] for v in parts.values()}
    if NONFINITE in statuses:
        return NONFINITE
    return PASS if ok and statuses == {PASS} else FAIL


def sha_problem(path: Path, want: str, what: str) -> str | None:
    """Why ``path`` is not the pinned file (missing, or another sha256), or None."""
    if not path.is_file():
        return f"{what} {path} is missing"
    got = exploit.sha256_file(path)
    return None if got == want else f"{what} {path} has sha256 {got}, the settings pin {want}"


def paired_wins(trained: np.ndarray, script: np.ndarray, side: str) -> dict:
    """Paired by start, in wins of the trained side (holds for the Guard team, reaches for the Strike team):
    ``transfer.paired`` (hold-based) relabelled. Every game must be finished (then not holding = reaching)."""
    trained, script = np.asarray(trained), np.asarray(script)
    if (trained == RUNNING).any() or (script == RUNNING).any():
        raise ValueError("a game did not finish: paired counts need finished games")
    p = transfer_paired(script, trained)
    if side == "guard":
        both, t_only, s_only, neither = p["both_hold"], p["gained_here"], p["lost_here"], p["both_lost"]
    else:
        both, t_only, s_only, neither = p["both_lost"], p["lost_here"], p["gained_here"], p["both_hold"]
    return {"both": both, "trained_only": t_only, "script_only": s_only, "neither": neither,
            "games": int(trained.size), "sign_test_p": p["sign_test_p"]}


def check_replay_batch(pg: dict, record: dict, ref, n: int, side: str, expected: int, tol: float,
                       phase: str = "replay") -> dict:
    """A trained player's whole evaluation batch replayed: equal to its recorded per-game arrays (``record``: exact keys
    equal, closest approach within ``tol``; ``viz/replay3d.check_against_record``) and the trained cell's (cell 0) wins
    equal ``expected``; with the batch's paired starts, one for one and non-finite checks."""
    from ..viz import replay3d as r3
    check = r3.check_against_record(pg, record, tol_m=tol)
    k, m = win_count(exploit.slice_cell(pg, 0, n), side)
    parts = plumbing_controls(pg, ref, n, phase)
    status = control_status(parts, check["equal"] and k == int(expected))
    won = "holds" if side == "guard" else "reaches"
    return {"status": status, "games_compared": int(len(pg["outcome"])), "mismatches": check["mismatches"],
            "tol_m": tol, "trained": {"k": k, "n": m}, "expected": int(expected), "plumbing": parts,
            "detail": f"{'EQUAL' if check['equal'] else 'DIFFERENT'} {check['mismatches']}; trained {won} {k}/{m} "
                      f"(record {expected}); " + "; ".join(f"{key} {v['status']}" for key, v in parts.items())}


def check_script_cells(pg: dict, cells: list, ref, variant: str, n: int, ticks: int, is_script,
                       g_s: tuple | None = None, expected: int | None = None, phase: str = "x") -> dict:
    """Every script cell of the batch (``is_script(cell)``) equal to the reference game for game (``exploit.replay_ok``'s
    exact rule on any device) from the reference's own starts; with ``g_s``, that cell holding ``expected``."""
    rows, ok = {}, True
    want_starts = exploit.starts_sha(ref.starts_m[:n])
    for i, cell in enumerate(cells):
        if not is_script(cell):
            continue
        mine = exploit.slice_cell(pg, i, n)
        theirs = {k: np.asarray(v)[:n] for k, v in ref.cell(variant, *cell).items()}
        same, text = exploit.replay_ok(mine, theirs, EXACT_RULE, {}, ticks_cap=ticks)
        starts = pg["start_sha256"][i] == want_starts
        rows[f"{cell[0]} v {cell[1]}"] = {"equal": bool(same and starts), "starts_equal": bool(starts), "detail": text}
        ok &= same and starts
    parts = plumbing_controls(pg, ref, n, phase)
    detail = "; ".join(f"{k}: {'ok' if v['equal'] else 'DIFFERS'} ({v['detail']})" for k, v in rows.items())
    named = {}
    if g_s is not None:
        holds = exploit.counts(exploit.slice_cell(pg, cells.index(tuple(g_s)), n))["holds"]
        ok &= holds == int(expected)
        named = {"screen_holds": holds, "expected": int(expected)}
        detail += f"; {g_s[0]} v {g_s[1]} holds {holds} (reference {expected})"
    return {"status": control_status(parts, ok), "cells": rows, **named, "plumbing": parts,
            "detail": detail + "; " + "; ".join(f"{key} {v['status']}" for key, v in parts.items())}


def end_reasons(cell_pg: dict, game_ticks: int) -> dict:
    """How the games of one cell ended (``END_REASONS``): a reach; a hold with every Strike drone tagged; a hold at the
    game's clock (end step at ``game_ticks`` or later, sweep.hold_composition's rule); any other hold; unfinished."""
    outcome = np.asarray(cell_pg["outcome"])
    end = np.asarray(cell_pg["end_step"])
    hold = outcome == GUARD_WIN
    tagged = hold & (np.asarray(cell_pg["strikes_left"]) == 0)
    clock = hold & ~tagged & (end >= int(game_ticks))
    return {"reach": int(np.sum(outcome == STRIKE_WIN)), "all_strikes_tagged": int(tagged.sum()),
            "clock": int(clock.sum()), "other_hold": int(np.sum(hold & ~tagged & ~clock)),
            "unfinished": int(np.sum(outcome == RUNNING))}


def length_median_s(cell_pg: dict) -> float | None:
    """Median length (s) of the cell's finished games, None if none finished (sweep.hold_composition's quantile)."""
    return sweep.hold_composition(cell_pg, 0)["length_median_s"]


def save_batch(path: Path, pg: dict) -> None:
    """The batch's per-game arrays plus its start hashes and game length (enough to rebuild the results on a resume)."""
    arrays = {k: v for k, v in pg.items() if isinstance(v, np.ndarray)}
    np.savez_compressed(path, **arrays, start_sha256=np.array(pg["start_sha256"]), game_ticks=np.array(pg["game_ticks"]))


def load_batch(path: Path) -> dict:
    with np.load(path) as d:
        pg = {k: d[k] for k in d.files}
    pg["start_sha256"] = [str(x) for x in pg["start_sha256"]]
    pg["game_ticks"] = int(pg["game_ticks"])
    return pg


# ================================================================================================ L1.14: the time-left test
def parse_time_left(spec) -> dict:
    """[player] time_left of the score tool (spec L1_SIDE_TRACK_SPEC addendum 2): a table with exactly one of
    ``offset_s`` (finite, 0 or more, a whole number of ticks of ``TICK_S``) or ``clamp_max_s`` (finite, above 0).
    Returns {"offset_s": float, "offset_ticks": int} or {"clamp_max_s": float}; ValueError names what is wrong."""
    if not isinstance(spec, dict):
        raise ValueError(f"[player] time_left must be a table, {{ offset_s = <s> }} or {{ clamp_max_s = <s> }}, got {spec!r}")
    if len(spec) != 1 or next(iter(spec)) not in TIME_LEFT_KEYS:
        raise ValueError(f"[player] time_left takes exactly one of {list(TIME_LEFT_KEYS)}, got {sorted(spec)}")
    (key, value), = spec.items()
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"[player] time_left.{key} must be a number of seconds, got {value!r}")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"[player] time_left.{key} must be finite, got {value!r}")
    if key == "clamp_max_s":
        if not value > 0:
            raise ValueError(f"[player] time_left.clamp_max_s must be above 0 s, got {value!r}")
        return {"clamp_max_s": value}
    if value < 0:
        raise ValueError(f"[player] time_left.offset_s must be 0 s or more, got {value!r}")
    ticks = value / TICK_S
    if abs(ticks - round(ticks)) > WHOLE_TICK_TOL:
        raise ValueError(f"[player] time_left.offset_s must be a whole number of ticks of {TICK_S} s, got {value!r} "
                         f"({ticks} ticks)")
    return {"offset_s": value, "offset_ticks": int(round(ticks))}


def time_left_text(override: dict) -> str:
    """The override in words, for titles and readings."""
    if "offset_s" in override:
        return f"time-left input + {override['offset_s']:g} s"
    return f"time-left input clamped to at most {override['clamp_max_s']:g} s"


class TimeLeftOverride:
    """A player whose network sees another time left (L1.14): the column ``ObsView.time_left`` of every in-game drone
    (alive column not 0) is changed before ``inner.act``; every other input, and every input of a drone that is out (all
    zeros but team), is passed unchanged. Batched over games and drones; the caller's tensor is not modified.

    ``offset_s``: the time left a game ``offset_ticks`` ticks longer shows, computed as the game computes its own
    (``core/game._time_left_s``: whole ticks left x ``TICK_S`` in float32), so the value is bit for bit that game's (a
    float add of the seconds would differ in the last bit at about one tick in five). ``clamp_max_s``: at most that."""

    def __init__(self, inner, override: dict):
        self.inner, self.override = inner, dict(override)
        self.team, self.name = inner.team, inner.name

    def reset(self, games: Tensor) -> None:
        self.inner.reset(games)

    def time_left(self, time_left_s: Tensor) -> Tensor:
        """The time left the network sees, from the game's [...] (seconds)."""
        if "offset_ticks" in self.override:
            ticks_left = torch.round(time_left_s / TICK_S).to(torch.long) + int(self.override["offset_ticks"])
            return (ticks_left.to(torch.float32) * TICK_S).to(time_left_s.dtype)
        return torch.clamp(time_left_s, max=float(self.override["clamp_max_s"]))

    def act(self, obs: Tensor) -> Tensor:
        """obs [N, K, D] -> the inner player's [N, K, 4]."""
        col = obs[..., ObsView.time_left]
        seen = torch.where(obs[..., ObsView.alive] != 0, self.time_left(col), col)
        changed = obs.clone()
        changed[..., ObsView.time_left] = seen
        return self.inner.act(changed)


def check_offset_prefix(cell_pg: dict, own_cell: dict, game_ticks: int, ticks_cap: int) -> dict:
    """Control c_offset (L1.14): the trained cell played on a game ``game_ticks`` long with the time left offset to the
    player's own game length (``cell_pg``) against its own evaluation's trained cell on the same starts (``own_cell``).
    It checks the reaches before the short game's end only (tags, holds and the rest of each game are not compared).
    PASS: every game of ``own_cell`` that reached by tick T = min(``game_ticks``, ``ticks_cap``) (end step at or below
    it; a reach on the last tick beats the clock, core/game) reaches at the same tick, no other game reaches, and every
    game finished (unfinished games are allowed only when the play cap ``ticks_cap`` is below the game length: tests)."""
    o, e = np.asarray(cell_pg["outcome"]), np.asarray(cell_pg["end_step"])
    ro, re = np.asarray(own_cell["outcome"]), np.asarray(own_cell["end_step"])
    if o.shape != ro.shape:
        raise ValueError(f"c_offset compares {o.shape} games with {ro.shape}")
    cut = min(int(game_ticks), int(ticks_cap))
    want = (ro == STRIKE_WIN) & (re <= cut)
    got = o == STRIKE_WIN
    same = want & got & (e == re)
    shifted = want & got & (e != re)
    extra, missing = got & ~want, want & ~got
    unfinished = int(np.sum(o == RUNNING))
    ok = not extra.any() and not missing.any() and not shifted.any() and (unfinished == 0 or cut < int(game_ticks))
    first = lambda mask: [int(i) for i in np.flatnonzero(mask)[:GAMES_SHOWN]]      # noqa: E731
    return {"status": PASS if ok else FAIL, "game_ticks": int(game_ticks), "ticks_cap": int(ticks_cap),
            "games": int(o.size),
            "reaches_expected": int(want.sum()), "reaches": int(got.sum()), "same_tick": int(same.sum()),
            "shifted": int(shifted.sum()), "extra": int(extra.sum()), "missing": int(missing.sum()),
            "unfinished": unfinished, "first_games": {"shifted": first(shifted), "extra": first(extra),
                                                      "missing": first(missing)},
            "detail": f"own evaluation: {int(want.sum())} reaches by tick {cut}; offset games: "
                      f"{int(got.sum())} reaches, {int(same.sum())} at the same tick, {int(shifted.sum())} at another "
                      f"tick, {int(extra.sum())} extra, {int(missing.sum())} missing, {unfinished} unfinished"}


# ================================================================================================ L1.15: the delay check
NO_REFERENCE = "no screen reference for this game: script cells reported, not compared (INFO)"


def _finite_stats(values: np.ndarray, prefix: str) -> dict:
    v = values[np.isfinite(values)]
    return {f"{prefix}_min_m": float(v.min()) if v.size else None,
            f"{prefix}_median_m": float(np.median(v)) if v.size else None}


def tag_stats(cell_pg: dict) -> dict:
    """Spec addendum 3 (L1.15), over the FINISHED first games of one cell (3-D distances, m):
    - ``tag_distance``: the distance at each tag (``tag_pair_m`` [n, S], finite where a Strike drone was tagged; pooled
      over games and drones), minimum and median;
    - ``closest_any_pair``: per game the closest approach of any opposite pair = min(its tag distances, ``closest_3d_m``),
      minimum and median over games. Needed because ``closest_3d_m`` is measured after the study tag has removed the
      tagged pair on that tick (core/game.py), so it never sees a tag's own distance;
    - ``closest_never_tagged``: ``closest_3d_m`` itself, the closest approach of pairs not removed by a tag on that tick.
    None where there is nothing to measure."""
    finished = np.asarray(cell_pg["outcome"]) != RUNNING
    pair = np.asarray(cell_pg["tag_pair_m"], dtype=float)[finished]
    closest = np.asarray(cell_pg["closest_3d_m"], dtype=float)[finished]
    tag_min = pair.min(axis=1) if pair.size else np.full(closest.shape, np.inf)
    return {"tags": int(np.isfinite(pair).sum()), **_finite_stats(pair.ravel(), "tag_distance"),
            **_finite_stats(np.minimum(tag_min, closest), "closest_any_pair"),
            **_finite_stats(closest, "closest_never_tagged")}


def check_plumbing_only(pg: dict, ref, n: int, phase: str = "matrix") -> dict:
    """A batch on a game without a screen reference: only the plumbing controls (paired starts against ``ref``'s
    starts, tags one for one, no non-finite action); the script cells are reported, not compared."""
    parts = plumbing_controls(pg, ref, n, phase)
    return {"status": control_status(parts, True), "plumbing": parts, "reference_compared": False,
            "detail": f"{NO_REFERENCE}; " + "; ".join(f"{key} {v['status']}" for key, v in parts.items())}
