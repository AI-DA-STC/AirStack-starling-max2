"""Route 3, stage LS1: the distillation of the scripts into one skill network per team (plan
ste_learning/drafts/LS1_TASK_PLAN.md, merge M2). Task LS1-M2-T1: the gate file ``configs/ste_ls1/distil_gates.toml``
and its loader; task LS1-M2-T2: the collection (``CodeSchedule``, ``collect``, ``Rows``, ``keep``, ``round_seed``; see
"The collection" below); the fit and the report follow in task LS1-M2-T3.

:func:`load_distil_gates` reads the file's bytes once (its sha256 is of the same bytes, as ``exploit.load_gates``) and
checks it: every section and key of :data:`SECTIONS` required, none unknown (ValueError naming it), each value of its
type and range, no code default. The owner's keys (R38) are :data:`LIMIT_KEYS` and :data:`CONTROL_SIZE_KEYS`: each is a
``FILL_`` string (``exploit.FILL_MARK``) until the owner sets it, and :func:`unfilled_limits` lists those still
``FILL_``; a run of record refuses the file while that list is not empty (the drivers' rule). ``end_time_max_ticks``
is required and a number whatever ``end_time_gated`` says (design check of M2: no ``FILL_`` survives into a run of
record and nothing is typed). The loader also loads what the file pins by path, the skills gate file and cells.toml
(not their sha256: the drivers refuse a changed pin), builds each team's ``cells.CellSpec`` from the skills gate file,
and checks against them: ``[data] hold`` is the skills gate file's decision ticks; the game file is its base variant's;
the clip codes and the near-miss cells are the side's (a near-miss cell is one code of the side, its fixed cell, or a
cells.toml combination, against a script of the other team's ``[players]``; every near-miss arm of the side has a cell,
each switch player of ``opponents/perturbed.SWITCHES`` included).

The smoke rule (:data:`SMOKE_RULE`) is the design check's: under ``--smoke`` the drivers take their sizes from
``[smoke]``, so the file needs no smoke copy of any other key.

The collection (task LS1-M2-T2). One relabelling round plays ``games`` games of the skills gate file's base game for
``ticks`` ticks: the side flies a code schedule (:class:`CodeSchedule`), the other team the opponent pool of its
``[players]`` scripts (``pool.OpponentPool``, redrawn after each game). Each game draws a mode (uniform: one code on
every drone all game; mix: one free combination of ``cells.mixed_pool`` all game; random: a two-level choice drawn
every ``hold`` ticks from the game's own start, resolved by ``resolve_two_level``) and whether the network flies it
(``net_flown``, probability 1 - script_share). Every live drone of the side gives one row per tick (:class:`Rows`): its
observation and every script's command on it (the labels, always the scripts', also in net-flown games), the code it
flew, how long that code has been held, and whether a label jumped near that tick (``near_switch``). :func:`keep`
draws the rows a round keeps, weighted, without replacement, with a quota of rows that have a mate absent.
Per-round seeds come from :func:`round_seed` (a mixing function, never ``seed + round``: that would give round 3 the
``[report] seed``). Batched: the loops run over ticks, the K skills and the M drones only, never over games.

No tuned number lives here (tests/test_ste_literals.py): every value comes from the gate file."""
from __future__ import annotations

import hashlib
import math
import re
import tomllib
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

import torch
from torch import Tensor

from ..core.game import SvgGame
from ..core.observations import OBS_DIM
from ..opponents.perturbed import SWITCHES
from . import cells, exploit, pool, skill_net, skills, sweep
from .config import TASK_IDS

ROUTE = "LS"                                     # the route's phase key (C1): [run] task is one of its task IDs
VARIANT = "base"                                 # the skills gate file's variant whose game the network plays
SIDES = cells.SIDES
SHA256 = re.compile(r"[0-9a-f]{64}")
INTERVALS = (cells.NEWCOMBE,)                    # the interval methods built (M1-T7, OP-11)
CORRECTIONS = (cells.BONFERRONI,)                # the corrections over cells built (M1-T7, OP-11)
LIMIT_KEYS = ("cmd_rmse_max", "cmd_unused_max_abs", "cmd_zero_skill_max_abs", "flips_max_games", "cell_margin",
              "pooled_margin", "end_time_gated", "end_time_max_ticks")
LIMIT_BOOL = "end_time_gated"                    # the one owner key that is a yes or no
COUNT_KEYS = ("permuted_min_miss_cells", "unfitted_min_miss_cells")
NEAR_MISS_KINDS = ("bias", "rotate_deg", "noise")
CONTROL_SIZE_KEYS = COUNT_KEYS + tuple(f"near_miss.{k}" for k in NEAR_MISS_KINDS) + \
    tuple(f"near_miss.switch.{k}" for k in SWITCHES)
STOP_KEYS = ("control_fails", "not_distilled", "fix_round", "one_side_only")
SECTIONS = {
    "run": ("task", "device"),
    "source": ("skills_gates", "skills_gates_sha256", "cells", "cells_sha256", "scripted_sha256", "game_file",
               "game_sha256"),
    "data": ("games", "ticks_per_round", "hold", "uniform_share", "mix_share", "random_share", "absent_min_share",
             "keep_rows", "switch_jump", "switch_window_ticks", "switch_floor", "seed", "pool_seed"),
    "dagger": ("script_share",),
    "net": ("hidden", "zeroed_inputs", "std_floor"),
    "fit": ("epochs", "lr", "batch", "seed"),
    "report": ("games", "ticks", "seed", "hold_bins_ticks"),
    "clips": ("games", "keep", "codes", "seed", "max_ticks", "speed", "fps", "dpi"),
    "smoke": ("games", "rounds", "ticks", "read_games", "device"),
    "read": ("alpha", "interval", "correction", "path_times_s", "chunk_cells", "device", "near_miss_cells"),
    "limits": LIMIT_KEYS,
    "controls": COUNT_KEYS + ("near_miss",),
    "stop": STOP_KEYS,
}
NEAR_MISS_CELL_KEYS = ("codes", "opponent")
SMOKE_RULE = ("Under --smoke (job LS1.0, not of record): collection plays [smoke] games x ticks for the first [smoke] "
              "rounds entries of [dagger] script_share; keep() takes min(keep_rows, the rows collected) rows and an "
              "absent quota of at most the absent rows there are; the report plays [smoke] games and ticks; the clips "
              "play [smoke] games and ticks with at most one code; the read plays [smoke] read_games starts per cell; "
              "on [smoke] device.")


@dataclass(frozen=True)
class DistilGates:
    """The distillation gate file as loaded: ``path``, ``sha256`` (of the bytes read), one dict per section of
    :data:`SECTIONS` (as written), and what it pins by path: ``skills_gates`` (``exploit.ExploitGates``), ``cells``
    (cells.toml, ``cells.load_cells``) and ``specs`` {side: ``cells.CellSpec``} built from the skills gate file."""
    path: str
    sha256: str
    run: dict
    source: dict
    data: dict
    dagger: dict
    net: dict
    fit: dict
    report: dict
    clips: dict
    smoke: dict
    read: dict
    limits: dict
    controls: dict
    stop: dict
    skills_gates: exploit.ExploitGates
    cells: dict
    specs: dict


# ================================================================================================ value checks
def is_fill(value: Any) -> bool:
    """A value the owner has not set yet: a string starting ``FILL_``."""
    return isinstance(value, str) and value.startswith(exploit.FILL_MARK)


def _exact(table: Any, keys, where: str, what: str = "key") -> dict:
    if not isinstance(table, dict):
        raise ValueError(f"[{where}] must be a table, got {table!r}")
    unknown, missing = sorted(set(table) - set(keys)), sorted(set(keys) - set(table))
    if unknown:
        raise ValueError(f"unknown {what}(s) in [{where}]: {unknown}")
    if missing:
        raise ValueError(f"missing {what}(s) in [{where}]: {missing}")
    return table


def _is_number(v: Any) -> bool:
    return not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v)


def _positive(v: Any, what: str) -> float:
    if not _is_number(v) or v <= 0:
        raise ValueError(f"{what} must be a finite number above 0, got {v!r}")
    return float(v)


def _whole(v: Any, what: str, least: int = 1) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v < least:
        raise ValueError(f"{what} must be a whole number >= {least}, got {v!r}")
    return v


def _share(v: Any, what: str) -> float:
    if not _is_number(v) or not 0 <= v <= 1:
        raise ValueError(f"{what} must be a share in [0, 1], got {v!r}")
    return float(v)


def _text(v: Any, what: str) -> str:
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{what} must be a non-empty string, got {v!r}")
    return v


def _increasing(v: Any, what: str, check) -> list:
    if not isinstance(v, list) or not v:
        raise ValueError(f"{what} must be a non-empty list, got {v!r}")
    out = [check(x, what) for x in v]
    if any(b <= a for a, b in zip(out, out[1:])):
        raise ValueError(f"{what} must increase strictly, got {v!r}")
    return out


def _resolve(path: str) -> Path:
    """A relative path from the ``svg_training/`` root, an absolute one as is (C4's rule)."""
    p = Path(path)
    return p if p.is_absolute() else exploit.ROOT / p


# ================================================================================================ the sections
def _check_source(src: dict) -> None:
    for key in ("skills_gates", "cells", "game_file"):
        _text(src[key], f"[source] {key}")
    for key in ("skills_gates_sha256", "cells_sha256", "scripted_sha256", "game_sha256"):
        if not isinstance(src[key], str) or not SHA256.fullmatch(src[key]):
            raise ValueError(f"[source] {key} must be a sha256 (64 lowercase hex digits), got {src[key]!r}")


def _check_data(d: dict, dagger: dict, skills_gates: exploit.ExploitGates) -> None:
    for key in ("games", "ticks_per_round", "hold", "keep_rows", "switch_window_ticks"):
        _whole(d[key], f"[data] {key}")
    shares = [_share(d[k], f"[data] {k}") for k in ("uniform_share", "mix_share", "random_share")]
    if not math.isclose(sum(shares), 1.0):
        raise ValueError(f"[data] uniform_share + mix_share + random_share must be 1, got {sum(shares)!r}")
    _share(d["absent_min_share"], "[data] absent_min_share")
    _positive(d["switch_jump"], "[data] switch_jump")
    _positive(d["switch_floor"], "[data] switch_floor")
    decision = skills_gates.trainer["decision_ticks"]
    if d["hold"] != decision:
        raise ValueError(f"[data] hold must be the skills gate file's [trainer] decision_ticks ({decision}), got "
                         f"{d['hold']!r}")
    script_share = dagger["script_share"]
    if not isinstance(script_share, list) or not script_share:
        raise ValueError(f"[dagger] script_share must be a non-empty list of shares, got {script_share!r}")
    for v in script_share:
        _share(v, "[dagger] script_share")
    if script_share[0] != 1.0:
        raise ValueError(f"[dagger] script_share must start at 1.0 (round 0 is flown by the scripts), got "
                         f"{script_share!r}")


def _check_net_fit_report(net: dict, fit: dict, report: dict) -> None:
    hidden = net["hidden"]
    if not isinstance(hidden, list) or not hidden:
        raise ValueError(f"[net] hidden must be a non-empty list of layer widths, got {hidden!r}")
    for w in hidden:
        _whole(w, "[net] hidden")
    zeroed = net["zeroed_inputs"]
    if (not isinstance(zeroed, list) or any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < OBS_DIM
                                             for i in zeroed) or len(set(zeroed)) != len(zeroed)):
        raise ValueError(f"[net] zeroed_inputs must be distinct observation indices in [0, {OBS_DIM}), got {zeroed!r}")
    _positive(net["std_floor"], "[net] std_floor")
    _whole(fit["epochs"], "[fit] epochs")
    _whole(fit["batch"], "[fit] batch")
    _positive(fit["lr"], "[fit] lr")
    _whole(report["games"], "[report] games")
    _whole(report["ticks"], "[report] ticks")
    bins = _increasing(report["hold_bins_ticks"], "[report] hold_bins_ticks", lambda x, w: _whole(x, w, 0))
    if len(bins) < 2:
        raise ValueError(f"[report] hold_bins_ticks must hold at least two edges, got {bins!r}")


def _check_clips(clips: dict, specs: dict) -> None:
    for key in ("games", "keep", "max_ticks", "fps", "dpi"):
        _whole(clips[key], f"[clips] {key}")
    if clips["keep"] > clips["games"]:
        raise ValueError(f"[clips] keep ({clips['keep']}) must not exceed games ({clips['games']})")
    _positive(clips["speed"], "[clips] speed")
    _exact(clips["codes"], SIDES, "clips.codes")
    for side, codes in clips["codes"].items():
        players = specs[side].players
        if (not isinstance(codes, list) or not codes or len(set(codes)) != len(codes)
                or any(c not in players for c in codes)):
            raise ValueError(f"[clips] codes.{side} must be distinct codes of the {side} team's [players] {players}, "
                             f"got {codes!r}")


def _check_smoke(smoke: dict, dagger: dict) -> None:
    for key in ("games", "rounds", "ticks", "read_games"):
        _whole(smoke[key], f"[smoke] {key}")
    _text(smoke["device"], "[smoke] device")
    if smoke["rounds"] > len(dagger["script_share"]):
        raise ValueError(f"[smoke] rounds ({smoke['rounds']}) must not exceed the rounds of [dagger] script_share "
                         f"({len(dagger['script_share'])}): the smoke flies its first entries")


def _near_miss_cells(table: Any, g_cells: dict, specs: dict, skills_gates: exploit.ExploitGates) -> None:
    """Each side's near-miss cells (R2 OA-3): see the module docstring."""
    _exact(table, SIDES, "read.near_miss_cells")
    for side, entries in table.items():
        where = f"read.near_miss_cells.{side}"
        kinds = ", ".join(NEAR_MISS_KINDS)
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"[{where}] must list at least one cell: the near-miss arms {kinds} have no cell")
        spec = specs[side]
        combos = {tuple(c) for c in g_cells["mixed"][side]}
        gated = cells.gated_opponents(skills_gates, side)
        seen = set()
        for e in entries:
            _exact(e, NEAR_MISS_CELL_KEYS, where)
            codes = e["codes"]
            fixed = isinstance(codes, list) and len(codes) == 1 and codes[0] in spec.players
            if not fixed and not (isinstance(codes, list) and tuple(codes) in combos):
                raise ValueError(f"[{where}] codes {codes!r}: neither one code of the {side} team's [players] (a fixed "
                                 f"cell) nor a cells.toml [mixed] {side} combination")
            if e["opponent"] not in gated:
                raise ValueError(f"[{where}] opponent {e['opponent']!r}: not a script of the other team's [players] "
                                 f"{gated}")
            cell = (tuple(codes), e["opponent"])
            if cell in seen:
                raise ValueError(f"[{where}] the cell {cell} is repeated")
            seen.add(cell)
        for key, (team, code, _, _) in SWITCHES.items():
            if team == side and not any(code in e["codes"] for e in entries):
                raise ValueError(f"[{where}] no cell flies {code}: the near-miss switch arm near_miss.switch.{key} "
                                 f"would have no cell")


def _check_read(read: dict, g_cells: dict, specs: dict, skills_gates: exploit.ExploitGates) -> None:
    alpha = read["alpha"]
    if not _is_number(alpha) or not 0 < alpha < 1:
        raise ValueError(f"[read] alpha must be a number in (0, 1), got {alpha!r}")
    if read["interval"] not in INTERVALS:
        raise ValueError(f"[read] interval must be one of the methods built {INTERVALS}, got {read['interval']!r}")
    if read["correction"] not in CORRECTIONS:
        raise ValueError(f"[read] correction must be one of the corrections built {CORRECTIONS}, got "
                         f"{read['correction']!r}")
    _increasing(read["path_times_s"], "[read] path_times_s", _positive)
    _whole(read["chunk_cells"], "[read] chunk_cells")
    _text(read["device"], "[read] device")
    _near_miss_cells(read["near_miss_cells"], g_cells, specs, skills_gates)


def _check_owner(limits: dict, controls: dict) -> None:
    """The owner's keys: ``FILL_`` or a value of their kind (R38)."""
    for key in LIMIT_KEYS:
        v = limits[key]
        if is_fill(v):
            continue
        if key == LIMIT_BOOL:
            if not isinstance(v, bool):
                raise ValueError(f"[limits] {key} must be true, false or a {exploit.FILL_MARK} string, got {v!r}")
        elif not _is_number(v) or v <= 0:
            raise ValueError(f"[limits] {key} must be a finite number above 0 or a {exploit.FILL_MARK} string, got "
                             f"{v!r}")
    for key in COUNT_KEYS:
        if not is_fill(controls[key]):
            _whole(controls[key], f"[controls] {key} (or a {exploit.FILL_MARK} string)")
    near = _exact(controls["near_miss"], NEAR_MISS_KINDS + ("switch",), "controls.near_miss")
    _exact(near["switch"], tuple(SWITCHES), "controls.near_miss.switch")
    values = {k: near[k] for k in NEAR_MISS_KINDS} | dict(near["switch"])
    for key, v in values.items():
        if not is_fill(v) and (not _is_number(v) or v <= 0):
            raise ValueError(f"[controls] near_miss {key} must be a finite number above 0 (in its player's unit for a "
                             f"switch) or a {exploit.FILL_MARK} string, got {v!r}")


# ================================================================================================ the loader
def load_distil_gates(path: str | Path) -> DistilGates:
    """Load and check the distillation gate file (see the module docstring); ValueError names the first problem."""
    path = Path(path)
    raw = path.read_bytes()
    data = tomllib.loads(raw.decode())
    _exact(data, SECTIONS, path.name, "section")
    parts = {name: _exact(data[name], keys, name) for name, keys in SECTIONS.items()}
    run, src = parts["run"], parts["source"]
    if run["task"] not in TASK_IDS[ROUTE]:
        raise ValueError(f"[run] task must be one of the route's task IDs {TASK_IDS[ROUTE]}, got {run['task']!r}")
    _text(run["device"], "[run] device")
    _check_source(src)
    skills_gates = exploit.load_gates(_resolve(src["skills_gates"]))
    g_cells = cells.load_cells(_resolve(src["cells"]))
    specs = {side: cells.cell_spec(skills_gates, side) for side in SIDES}
    for side, spec in specs.items():
        problem = cells.check_cells(spec, g_cells, skills_gates)
        if problem:
            raise ValueError(problem)
    base = skills_gates.games[skills_gates.variants[VARIANT]["game"]]
    if (src["game_file"], src["game_sha256"]) != (base.file, base.sha256):
        raise ValueError(f"[source] game_file and game_sha256 must be the skills gate file's {VARIANT} game "
                         f"({base.file}, {base.sha256}), got ({src['game_file']}, {src['game_sha256']})")
    _check_data(parts["data"], parts["dagger"], skills_gates)
    _check_net_fit_report(parts["net"], parts["fit"], parts["report"])
    _check_clips(parts["clips"], specs)
    _check_smoke(parts["smoke"], parts["dagger"])
    seeds = {"[data] seed": parts["data"]["seed"], "[data] pool_seed": parts["data"]["pool_seed"],
             "[fit] seed": parts["fit"]["seed"], "[report] seed": parts["report"]["seed"],
             "[clips] seed": parts["clips"]["seed"]}
    for what, s in seeds.items():
        _whole(s, what, 0)
    if len(set(seeds.values())) != len(seeds):
        raise ValueError(f"the seeds must differ: {seeds}")
    _check_read(parts["read"], g_cells, specs, skills_gates)
    _check_owner(parts["limits"], parts["controls"])
    for key in STOP_KEYS:
        _text(parts["stop"][key], f"[stop] {key}")
    return DistilGates(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), skills_gates=skills_gates,
                       cells=g_cells, specs=specs, **parts)


def _owner_value(controls: dict, key: str) -> Any:
    node = controls
    for part in key.split("."):
        node = node[part]
    return node


def unfilled_limits(g: DistilGates) -> list[str]:
    """The owner's keys still ``FILL_``, by name: ``limits.<key>`` in :data:`LIMIT_KEYS` order, then
    ``controls.<key>`` in :data:`CONTROL_SIZE_KEYS` order (``controls.near_miss.switch.<key>`` for a switch)."""
    out = [f"limits.{k}" for k in LIMIT_KEYS if is_fill(g.limits[k])]
    return out + [f"controls.{k}" for k in CONTROL_SIZE_KEYS if is_fill(_owner_value(g.controls, k))]


# ================================================================================================ the collection (T2)
MODES = ("uniform", "mix", "random")             # a game's mode; Rows.mode and CodeSchedule.mode hold the index
UNIFORM, MIX, RANDOM = 0, 1, 2
SEED_PURPOSES = ("game", "schedule", "pool")     # round_seed's purposes: the game's starts, the schedule, the pool
_SEED_BITS = 63
SEED_RANGE = (1 << _SEED_BITS) - 1               # round seeds lie in [0, SEED_RANGE): non-negative, below 2^63
HOST_COPY_TICKS = 64                             # ticks of rows copied to the CPU at once (memory only, not a result)
ROW_FIELDS = ("obs", "slot", "label", "flown", "n_live", "held", "mode", "net_flown", "near_switch", "round", "game",
              "episode", "tick", "opponent")


def round_seed(seed: int, round_index: int, purpose: str) -> int:
    """The seed of one purpose (:data:`SEED_PURPOSES`) of relabelling round ``round_index`` under ``seed``: the
    splitmix64 mixing of ``pool.pool_draw`` keyed by (seed, round, purpose), in [0, SEED_RANGE). Never ``seed + round``
    (design check of M2: four rounds from [data] seed 150001 would reach [report] seed 150004)."""
    if purpose not in SEED_PURPOSES:
        raise ValueError(f"purpose must be one of {SEED_PURPOSES}, got {purpose!r}")
    r = torch.tensor([int(round_index)], dtype=torch.long)
    p = torch.tensor([SEED_PURPOSES.index(purpose)], dtype=torch.long)
    return int(pool.pool_draw(int(seed), r, p, SEED_RANGE)[0])


def mix_combos(spec: cells.CellSpec, device) -> Tensor:
    """The mix mode's combinations [C, M] long: every free combination of ``cells.mixed_pool(spec)`` (at least two
    distinct drone skills; Guard 24, Strike 60 in 3v3) as code indices of ``spec.players``."""
    rows = [[spec.players.index(s) for s in c] for c in cells.mixed_pool(spec)]
    return torch.tensor(rows, dtype=torch.long, device=torch.device(device)).reshape(len(rows), spec.drones)


@dataclass(frozen=True)
class Rows:
    """The rows of a collection, on the CPU, one per live drone of the side per tick (R rows, time-major):
    ``obs`` [R, OBS_DIM] f32; ``slot`` [R] i64 (the drone's index in its team); ``label`` [R, K, 4] f32 (every script's
    command on that state, code order); ``flown`` [R] i64 (the code the drone flew); ``n_live`` [R] i8 (live drones of
    the side at that tick); ``held`` [R] i16 (ticks the flown code had been flown before this tick, in this game: 0 on
    the game's first tick and on the tick it changed); ``mode`` [R] i8 (:data:`MODES` index); ``net_flown`` [R] bool;
    ``near_switch`` [R] bool; ``round`` [R] i8; and, for the checks and the report: ``game`` [R] i32 (the game slot),
    ``episode`` [R] i32 (the slot's game counter, 0 first, the opponent pool's counter), ``tick`` [R] i16 (the game's
    tick), ``opponent`` [R] i8 (the index of the game's opponent in the pool's list). ``team_size``: M, the side's
    drones per game (a row has a mate absent when ``n_live < team_size``)."""
    obs: Tensor
    slot: Tensor
    label: Tensor
    flown: Tensor
    n_live: Tensor
    held: Tensor
    mode: Tensor
    net_flown: Tensor
    near_switch: Tensor
    round: Tensor
    game: Tensor
    episode: Tensor
    tick: Tensor
    opponent: Tensor
    team_size: int

    def absent(self) -> Tensor:
        """[R] bool: a mate of the drone was absent (out of the game) at that tick."""
        return self.n_live.to(torch.long) < self.team_size


class CodeSchedule:
    """The codes the side flies, per game and drone (task LS1-M2-T2; plan M2-T2 with the design check's changes).

    spec: the side's ``cells.CellSpec``; dispatch: the side's ``skills.TwoLevelDispatch`` (its ``widths`` and
    ``resolve_two_level``); shares: (uniform, mix, random), each in [0, 1], summing to 1; combos: [C, M] long code
    indices (:func:`mix_combos`); hold: the random mode's decision ticks (>= 1); script_share: the probability a game is
    flown by the scripts (``net_flown`` ~ Bernoulli(1 - script_share)); device; seed: the schedule's own
    ``torch.Generator`` seed (:func:`round_seed` of the round, purpose "schedule").

    State, per game [N] and per drone [N, M] (allocated by the first ``new_games``, N = its mask's length): ``mode``,
    ``net_flown``, ``tick`` (the game's own tick: ``SvgGame.step`` restarts an ended game itself, so one scalar tick
    cannot phase from each game's start), ``current`` [N, M] (the code each drone flies), ``held`` [N, M].
    :meth:`new_games` (mask [N] bool) draws a game's mode, code, combination row and ``net_flown``, and restarts its
    tick; the draws are made for every game and kept where ``mask`` (no per-game loop; the stream does not depend on
    which games end). :meth:`flown` (obs [N, M, D]) returns the codes of this tick [N, M] long and advances the tick: a
    random game draws a (team index, drone index) per drone at ``tick % hold == 0`` and resolves it on that tick's
    observation (the leader is the lowest-index live drone); the resolved code is held to the next decision."""

    def __init__(self, spec: cells.CellSpec, dispatch: skills.TwoLevelDispatch, shares, combos: Tensor, hold: int,
                 script_share: float, device, seed: int):
        shares = tuple(float(x) for x in shares)
        if len(shares) != len(MODES) or any(not 0 <= x <= 1 for x in shares) or not math.isclose(sum(shares), 1.0):
            raise ValueError(f"shares must be {len(MODES)} shares {MODES} summing to 1, got {shares!r}")
        if isinstance(hold, bool) or not isinstance(hold, int) or hold < 1:
            raise ValueError(f"hold must be a whole number >= 1, got {hold!r}")
        if not 0 <= float(script_share) <= 1:
            raise ValueError(f"script_share must be a share in [0, 1], got {script_share!r}")
        if combos.dim() != 2 or combos.shape[1] != spec.drones or (shares[MIX] > 0 and combos.shape[0] == 0):
            raise ValueError(f"combos must be [C, {spec.drones}] with C >= 1 when the mix share is above 0, got "
                             f"{tuple(combos.shape)}")
        if dispatch.team != spec.side:
            raise ValueError(f"the dispatch is the {dispatch.team} team's, the schedule the {spec.side} team's")
        self.spec, self.dispatch, self.hold, self.script_share = spec, dispatch, hold, float(script_share)
        self.device = torch.device(device)
        self.combos = combos.to(self.device, torch.long)
        self.cum = (shares[UNIFORM], shares[UNIFORM] + shares[MIX])
        self.gen = torch.Generator(device=self.device)
        self.gen.manual_seed(int(seed))
        self.mode = self.net_flown = self.tick = self.current = self.held = None

    def _alloc(self, n: int) -> None:
        m, dev = self.spec.drones, self.device
        self.mode = torch.zeros(n, dtype=torch.long, device=dev)
        self.net_flown = torch.zeros(n, dtype=torch.bool, device=dev)
        self.tick = torch.zeros(n, dtype=torch.long, device=dev)
        self.current = torch.zeros(n, m, dtype=torch.long, device=dev)
        self.held = torch.zeros(n, m, dtype=torch.long, device=dev)

    def new_games(self, mask: Tensor) -> None:
        """mask [N] bool: new games start in these slots (draws for every game, kept where ``mask``)."""
        if self.tick is None:
            self._alloc(mask.shape[0])
        n, dev, g = mask.shape[0], self.device, self.gen
        u_mode = torch.rand(n, generator=g, device=dev)
        code = torch.randint(len(self.spec.players), (n,), generator=g, device=dev)
        row = torch.randint(max(self.combos.shape[0], 1), (n,), generator=g, device=dev)
        u_net = torch.rand(n, generator=g, device=dev)
        mode = (u_mode >= self.cum[0]).long() + (u_mode >= self.cum[1]).long()
        mixed = self.combos[row] if self.combos.shape[0] else self.current
        start = torch.where((mode == UNIFORM)[:, None], code[:, None].expand(-1, self.spec.drones), mixed)
        self.mode = torch.where(mask, mode, self.mode)
        self.net_flown = torch.where(mask, u_net < 1.0 - self.script_share, self.net_flown)
        self.current = torch.where(mask[:, None], start, self.current)
        self.tick = torch.where(mask, torch.zeros_like(self.tick), self.tick)
        self.held = torch.where(mask[:, None], torch.zeros_like(self.held), self.held)

    def flown(self, obs: Tensor) -> Tensor:
        """obs [N, M, D] (the side's, this tick) -> the codes flown this tick [N, M] long; advances each game's tick."""
        n, m = obs.shape[:2]
        t_width, d_width = self.dispatch.widths
        team_a = torch.randint(t_width, (n, m), generator=self.gen, device=self.device)
        drone_a = torch.randint(d_width, (n, m), generator=self.gen, device=self.device)
        drawn, _ = self.dispatch.resolve_two_level(torch.stack((team_a, drone_a), dim=-1), obs)
        decide = (self.mode == RANDOM) & (self.tick % self.hold == 0)
        new = torch.where(decide[:, None], drawn, self.current)
        restart = (self.tick == 0)[:, None] | (new != self.current)
        self.held = torch.where(restart, torch.zeros_like(self.held), self.held + 1)
        self.current = new
        self.tick = self.tick + 1
        return new


def _check_net(net, side: str, spec: cells.CellSpec, script_share: float) -> None:
    if net is None:
        if float(script_share) != 1.0:
            raise ValueError(f"net=None needs script_share 1.0 (every game flown by the scripts), got {script_share!r}")
        return
    if net.team != side:
        raise ValueError(f"the network is the {net.team} team's, the collection the {side} team's")
    if tuple(net.skills) != tuple(spec.players):
        raise ValueError(f"the network's skills {list(net.skills)} are not the {side} team's [players] "
                         f"{list(spec.players)}")


def _host_rows(chunk: list[dict]) -> dict:
    """One chunk of ticks (each a dict of [N, M, ...] tensors with ``live`` [N, M]) -> its live rows on the CPU (one
    selection and one host copy per field per chunk)."""
    live = torch.stack([c["live"] for c in chunk])                                    # [T, N, M]
    return {k: torch.stack([c[k] for c in chunk])[live].cpu() for k in chunk[0] if k != "live"}


def collect(cfg, spec: cells.CellSpec, players: dict, side: str, net, script_share: float, games: int, ticks: int,
            hold: int, seed: int, pool_seed: int, device, should_stop: Callable[[], bool] | None = None, *,
            size: str, shares, switch_jump: float, switch_window_ticks: int, round_index: int) -> Rows:
    """One relabelling round's rows (module docstring, "The collection").

    cfg: the game (``exploit.variant_cfg(skills_gates, "base")``); spec: the side's ``cells.CellSpec``; players: the
    skills gate file's ``[players]``; side: the team that flies the codes; net: the side's ``skill_net.SkillNet`` (or a
    stand-in of C2's call), None only with ``script_share`` 1.0 (ValueError); games, ticks: the batch and its length;
    hold: the random mode's decision ticks; seed, pool_seed: the round's base seeds (the game's starts and the schedule
    from ``seed``, the pool from ``pool_seed``, each through :func:`round_seed` of ``round_index``); device;
    should_stop: asked before every tick, yes raises ``sweep.SweepStopped``. Keyword-only (the design check's additions
    to the plan's signature): size ("3v3", the skills gate file's ``[run] size``), shares (uniform, mix, random),
    switch_jump, switch_window_ticks, round_index.

    Per tick: the codes (``CodeSchedule.flown``), every script's command on the side's observation (the labels), the
    action (script-flown games ``gather(label, flown)``, net-flown games ``skill_net.one_code(net, obs, flown)``, one
    ``torch.where``), the near-switch countdown, the rows; then ``SvgGame.step``, and for the games that ended
    (``out.done``, restarted by the step) a new schedule draw, a pool redraw, and the switch state cleared."""
    _check_net(net, side, spec, script_share)
    guards, strikes = sweep.parse_size(size)
    if (guards if side == cells.SIDES[0] else strikes) != spec.drones:
        raise ValueError(f"size {size!r} does not give the {side} team its {spec.drones} drones")
    if isinstance(switch_window_ticks, bool) or not isinstance(switch_window_ticks, int) or switch_window_ticks < 1:
        raise ValueError(f"switch_window_ticks must be a whole number >= 1, got {switch_window_ticks!r}")
    dev, other = torch.device(device), cells.other(side)
    game_seed = round_seed(seed, round_index, "game")
    game = SvgGame(cfg, games, guards, strikes, device=str(dev), seed=game_seed)
    dispatch = skills.TwoLevelDispatch(side, list(spec.players), list(spec.team_strategies), list(spec.drone_skills),
                                       cfg, games, dev, game_seed)
    opponents = pool.OpponentPool(other, pool.pool_members(players, other), cfg, games, dev,
                                  round_seed(pool_seed, round_index, "pool"))
    sched = CodeSchedule(spec, dispatch, shares, mix_combos(spec, dev), hold, script_share, dev,
                         round_seed(seed, round_index, "schedule"))
    m = spec.drones
    obs = game.reset()
    every = torch.ones(games, dtype=torch.bool, device=dev)
    sched.new_games(every)
    opponents.reset(every)
    dispatch.reset(every)
    flies_net = net is not None and float(script_share) < 1.0
    game_idx = torch.arange(games, device=dev)[:, None].expand(-1, m)
    slot = torch.arange(m, device=dev)[None, :].expand(games, -1)
    episode = torch.zeros(games, dtype=torch.long, device=dev)
    countdown = torch.zeros(games, m, dtype=torch.long, device=dev)
    prev_live = torch.zeros(games, m, dtype=torch.bool, device=dev)
    prev_label = None
    parts, chunk = [], []
    for _ in range(int(ticks)):
        if should_stop is not None and should_stop():
            raise sweep.SweepStopped("stop requested before a tick")
        own = obs[side]
        tick = sched.tick.clone()
        flown = sched.flown(own)                                                   # [N, M]
        label = dispatch.commands(own)                                             # [N, M, K, 4]
        idx = flown[:, :, None, None].expand(-1, -1, 1, label.shape[-1])
        action = torch.gather(label, 2, idx)[:, :, 0]
        if flies_net:
            action = torch.where(sched.net_flown[:, None, None], skill_net.one_code(net, own, flown), action)
        live = own[..., skills._V.alive] > skills.ALIVE_FLAG_MIN                   # [N, M]
        if prev_label is not None:
            jump = (label - prev_label).abs().amax(dim=(-1, -2)) > switch_jump
            countdown = torch.where(prev_live & live & jump, torch.full_like(countdown, switch_window_ticks),
                                    (countdown - 1).clamp(min=0))
        n_live = live.sum(dim=1, keepdim=True).expand(-1, m)
        chunk.append({"live": live, "obs": own, "slot": slot, "label": label, "flown": flown,
                      "n_live": n_live.to(torch.int8), "held": sched.held.to(torch.int16),
                      "mode": sched.mode[:, None].expand(-1, m).to(torch.int8),
                      "net_flown": sched.net_flown[:, None].expand(-1, m), "near_switch": countdown > 0,
                      "game": game_idx.to(torch.int32), "episode": episode[:, None].expand(-1, m).to(torch.int32),
                      "tick": tick[:, None].expand(-1, m).to(torch.int16),
                      "opponent": opponents.draw[:, None].expand(-1, m).to(torch.int8)})
        if len(chunk) == HOST_COPY_TICKS:
            parts.append(_host_rows(chunk))
            chunk = []
        out = game.step({side: action, other: opponents.act(obs[other])})
        done = out.done
        opponents.redraw(done)
        sched.new_games(done)
        episode = episode + done.to(torch.long)
        countdown = torch.where(done[:, None], torch.zeros_like(countdown), countdown)
        prev_live = live & ~done[:, None]
        prev_label = label
        obs = out.obs
    if chunk:
        parts.append(_host_rows(chunk))
    k = len(spec.players)
    empty = {"obs": torch.zeros(0, OBS_DIM), "label": torch.zeros(0, k, skill_net.COMMAND_DIM)}
    cat = {}
    for name in ROW_FIELDS:
        if name == "round":
            continue
        cat[name] = torch.cat([p[name] for p in parts]) if parts else empty.get(name, torch.zeros(0, dtype=torch.long))
    r = cat["obs"].shape[0]
    return Rows(**cat, round=torch.full((r,), int(round_index), dtype=torch.int8), team_size=m)


def _weighted(mask: Tensor, count: int, w: Tensor, log_u: Tensor, u: Tensor) -> Tensor:
    """``count`` distinct row indices among ``mask`` [R] bool: weighted without replacement by the keys
    ``log(1 - u) / w`` (Efraimidis and Spirakis 2006, in logs, float64) among the rows of positive weight; when these are
    fewer than ``count``, all of them and then the rest among the zero-weight rows of ``mask``, uniform (by ``u``)."""
    if count <= 0:
        return torch.zeros(0, dtype=torch.long)
    neg_inf = torch.tensor(float("-inf"), dtype=torch.float64)
    positive = mask & (w > 0)
    take = min(count, int(positive.sum()))
    keys = torch.where(positive, log_u / torch.where(positive, w, torch.ones_like(w)), neg_inf)
    out = torch.topk(keys, take).indices if take else torch.zeros(0, dtype=torch.long)
    if count > take:
        zero = mask & ~positive
        fill = torch.where(zero, u, neg_inf)
        out = torch.cat((out, torch.topk(fill, count - take).indices))
    return out


def keep(rows: Rows, err: Tensor | None, keep_rows: int, absent_min_share: float, switch_floor: float,
         gen: torch.Generator) -> Tensor:
    """The rows a round keeps: ``k = min(keep_rows, R)`` distinct indices [k] i64, ascending, drawn without replacement
    with weights ``w = err / mean(err)`` (err [R], each row's error under the previous round's network, >= 0 and
    finite; None in round 0: w = 1; a zero mean: w = 1), raised to at least ``switch_floor`` on ``near_switch`` rows;
    stratified so that the rows with a mate absent are ``ceil(max(absent_min_share, their natural share) x k)``, at most
    the absent rows there are and at least what the other rows cannot fill (the smoke rule, :data:`SMOKE_RULE`). Each
    stratum is drawn by Efraimidis and Spirakis's keys in logs and float64 (``log(1 - u) / w``, ``topk``: no underflow
    of ``u ** (1 / w)``, no ``torch.multinomial`` limit of 2^24 categories); zero-weight rows only fill a stratum whose
    positive-weight rows are too few, and then at random. ``gen``: a CPU ``torch.Generator``."""
    r = rows.obs.shape[0]
    if isinstance(keep_rows, bool) or not isinstance(keep_rows, int) or keep_rows < 1:
        raise ValueError(f"keep_rows must be a whole number >= 1, got {keep_rows!r}")
    if not 0 <= absent_min_share <= 1:
        raise ValueError(f"absent_min_share must be a share in [0, 1], got {absent_min_share!r}")
    if not switch_floor > 0:
        raise ValueError(f"switch_floor must be above 0, got {switch_floor!r}")
    w = torch.ones(r, dtype=torch.float64)
    if err is not None:
        e = err.detach().to("cpu", torch.float64)
        if e.shape != (r,) or not bool(torch.isfinite(e).all()) or bool((e < 0).any()):
            raise ValueError(f"err must be [{r}] finite errors >= 0, got shape {tuple(e.shape)}")
        mean = e.mean() if r else e.new_zeros(())
        if float(mean) > 0:
            w = e / mean
    w = torch.where(rows.near_switch, w.clamp(min=float(switch_floor)), w)
    k = min(keep_rows, r)
    absent = rows.absent()
    n_abs = int(absent.sum())
    share = max(Fraction(str(absent_min_share)), Fraction(n_abs, r)) if r else Fraction(0)
    quota = min(n_abs, max(math.ceil(share * k), k - (r - n_abs)))
    u = torch.rand(r, generator=gen, dtype=torch.float64)
    log_u = torch.log1p(-u)
    idx = torch.cat((_weighted(absent, quota, w, log_u, u), _weighted(~absent, k - quota, w, log_u, u)))
    return idx.sort().values
