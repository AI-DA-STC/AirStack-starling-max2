"""Route 3, stage LS1: the distillation of the scripts into one skill network per team (plan
ste_learning/drafts/LS1_TASK_PLAN.md, merge M2). Task LS1-M2-T1: the gate file ``configs/ste_ls1/distil_gates.toml``
and its loader; collection, fit and report follow in tasks LS1-M2-T2 and T3.

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

No tuned number lives here (tests/test_ste_literals.py): every value comes from the gate file."""
from __future__ import annotations

import hashlib
import math
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.observations import OBS_DIM
from ..opponents.perturbed import SWITCHES
from . import cells, exploit
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
