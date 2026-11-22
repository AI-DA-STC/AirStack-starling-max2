"""Settings of STE's learning track: typed, frozen, TOML only (``configs/ste_learning.toml``).

Task L0.1 holds the track's process settings: which plan and phase, and the GPU-hour caps. Game settings live in
``configs/ste_game.toml`` (task L0.8 onwards), not here.

The caps come in budget sections, each one cap over one or more phases and a cap per task of those phases. ``[budget]``
holds phase L0's (``BUDGET_PHASES``; closed at gate G0, 22 Nov 2026, and kept under its first name so the L0 tools and
tests read it as before). Each later budget is a section ``[budget_<phases>]`` whose name spells its phases, as
``[budget_l1_l2]`` for the one cap of phases L1 and L2 together (owner, G0, 22 Nov 2026); it lists its ``phases``. Every
budget section says whether it is ``closed``: the caps of a closed section stay readable, but no task of it launches
(``ste/budget.py``), and the phase in work cannot be in one. The phase in work must be covered by a budget section; a
file written for phase L0 has ``[budget]`` only.

The loader fails closed: an unknown or missing section, key or task ID raises ``ValueError``, and so does a value of the
wrong type (a whole number where a decimal is expected, a yes/no where a number is expected). The dataclasses have no
defaults, so every number comes from the file; the file's sha256 is returned beside the settings so a run can record
which settings it used. Same pattern as ``core/game_config.py``, with type checks added.
"""
from __future__ import annotations

import hashlib
import math
import tomllib
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

from ..core.game_config import CONFIGS  # standard library only: no PyTorch, no Isaac

SETTINGS_FILE = CONFIGS / "ste_learning.toml"

# Task IDs of each phase the loader knows, in the order of its task table. Names, not numbers. L0: the table in
# ste_learning/PLAN.md section 4 (tests/test_ste_config.py reads the IDs out of PLAN.md and fails if this tuple or the
# file differs from it). L1: the lead's split of the costed draft (ste_learning/drafts/L1_L9_COSTED_PLAN_DRAFT.md
# section 3; PLAN.md has no L1 task table). L2: its task IDs are added when L2 starts.
TASK_IDS: dict[str, tuple[str, ...]] = {
    "L0": ("L0.1", "L0.7", "L0.8", "L0.9", "L0.10", "L0.11", "L0.12", "L0.2", "L0.13", "L0.3", "L0.4", "L0.5", "L0.14",
           "L0.6"),
    "L1": ("L1.0", "L1.1", "L1.2", "L1.3", "L1.4", "L1.5", "L1.6", "L1.7", "L1.8", "L1.9", "L1.10", "L1.11", "L1.12",
           "L1.13", "L1.14", "L1.15"),
    "L2": (),
}
BUDGET_PHASES: tuple[str, ...] = ("L0",)    # the phases [budget] covers (its first name, kept for the L0 tools)
_FIRST_BUDGET = "budget"
_LATER_BUDGET = "budget_"                   # a later budget section: "budget_" + its phases, lower case, joined by "_"


@dataclass(frozen=True)
class TrackCfg:
    """Which plan the settings belong to: the version of ste_learning/PLAN.md and the phase in work (a TASK_IDS key)."""
    plan_version: int
    phase: str


@dataclass(frozen=True)
class BudgetCfg:
    """GPU-hour caps of one budget section: one cap over its phases, and a cap per task of those phases.

    ``section``: the section's name in the file ("budget" or "budget_<phases>"). ``phases``: the phases the cap covers.
    ``closed``: true once those phases are closed (their caps stay readable; no task of them launches).
    ``phase_cap_gpu_h``: the most GPU-hours those phases may use together. ``task_cap_gpu_h``: one (task ID, cap in
    GPU-hours) pair per task of those phases, in TASK_IDS order; a tuple of pairs, so nothing in it can be changed after
    loading. The loader has checked that no cap is negative and that the task caps together do not exceed the phase cap.
    Caps are added and compared as the decimal numbers written in the file (0.1 + 0.2 is 0.3), not as binary floats.
    """
    section: str
    phases: tuple[str, ...]
    closed: bool
    phase_cap_gpu_h: float
    task_cap_gpu_h: tuple[tuple[str, float], ...]

    def cap_gpu_h(self, task_id: str) -> float:
        """The cap of one task in GPU-hours; ``KeyError`` for a task that is not in the phase."""
        for task, cap in self.task_cap_gpu_h:
            if task == task_id:
                return cap
        raise KeyError(f"no GPU-hour cap for task {task_id!r} in [{self.section}] "
                       f"(known: {[task for task, _ in self.task_cap_gpu_h]})")

    def task_caps_total_gpu_h(self) -> float:
        """The task caps added up in decimal, in GPU-hours (the float nearest to the exact decimal sum)."""
        return float(_decimal_sum(cap for _, cap in self.task_cap_gpu_h))


@dataclass(frozen=True)
class SteLearningCfg:
    """``budget``: the ``[budget]`` section, phase L0's caps (closed at G0; the L0 tools read L0 caps here).
    ``later_budgets``: the ``[budget_<phases>]`` sections, in the file's order."""
    track: TrackCfg
    budget: BudgetCfg
    later_budgets: tuple[BudgetCfg, ...]

    def budgets(self) -> tuple[BudgetCfg, ...]:
        """Every budget section, ``[budget]`` first."""
        return (self.budget, *self.later_budgets)

    def budget_in_work(self) -> BudgetCfg:
        """The budget section that covers the phase in work (the loader has checked there is one)."""
        return next(budget for budget in self.budgets() if self.track.phase in budget.phases)

    def budget_of(self, task_id: str) -> BudgetCfg:
        """The budget section that holds the cap of ``task_id``; ``KeyError`` for a task in none of them."""
        for budget in self.budgets():
            if any(task == task_id for task, _ in budget.task_cap_gpu_h):
                return budget
        raise KeyError(f"no GPU-hour cap for task {task_id!r} in any budget section (known: "
                       f"{[task for budget in self.budgets() for task, _ in budget.task_cap_gpu_h]})")

    def cap_gpu_h(self, task_id: str) -> float:
        """The cap of one task in GPU-hours, whichever budget section holds it; ``KeyError`` for an unknown task."""
        return self.budget_of(task_id).cap_gpu_h(task_id)


@dataclass(frozen=True)
class Provenance:
    """Where the settings came from: the file's path and the sha256 of its bytes (comments included)."""
    settings_file: str
    settings_sha256: str


def phase_of(task_id: str) -> str:
    """The phase a task belongs to, by TASK_IDS (whole IDs, never a prefix: "L10" is no L1 task); ``KeyError`` if none."""
    for phase, tasks in TASK_IDS.items():
        if task_id in tasks:
            return phase
    raise KeyError(f"task {task_id!r} is in no phase of TASK_IDS (ste/config.py)")


def _decimal(value: float) -> Fraction:
    """``value`` as the exact decimal number its shortest written form states: 0.1 is one tenth, exactly."""
    return Fraction(repr(value))


def _decimal_sum(values: Iterable[float]) -> Fraction:
    return sum((_decimal(value) for value in values), Fraction(0))


_KINDS = {int: "a whole number", float: "a decimal number (write 3.0, not 3)", str: "text in quotes",
          bool: "a yes/no (true or false)"}


def _typed(value: Any, kind: type, where: str) -> Any:
    """``value`` if it is exactly of ``kind``. Exact on purpose: a TOML yes/no is not a number, and 3 is not 3.0."""
    if type(value) is not kind:
        raise ValueError(f"{where} must be {_KINDS[kind]}, got {value!r}")
    return value


def _cap_gpu_h(value: Any, where: str) -> float:
    cap = _typed(value, float, where)
    if not math.isfinite(cap) or cap < 0:
        raise ValueError(f"{where} must be finite and not negative (GPU-hours), got {cap!r}")
    return cap


def _table(parent: dict[str, Any], name: str, where: str, keys: tuple[str, ...], what: str,
           hint: str = "") -> dict[str, Any]:
    """The table ``parent[name]`` once its keys are checked to be exactly ``keys``; ``what`` names a key in messages."""
    table = parent[name]
    if not isinstance(table, dict):
        raise ValueError(f"[{where}] must be a table, got {table!r}")
    _exact(table, keys, what, f"[{where}]", hint)
    return table


def _exact(table: dict[str, Any], keys: tuple[str, ...], what: str, where: str, hint: str = "") -> None:
    unknown = sorted(set(table) - set(keys))
    if unknown:
        raise ValueError(f"unknown {what}(s) in {where}: {unknown} (known: {list(keys)}){hint}")
    missing = [key for key in keys if key not in table]
    if missing:
        raise ValueError(f"missing {what}(s) in {where}: {missing}")


def _budget(data: dict[str, Any], section: str, phases: tuple[str, ...]) -> BudgetCfg:
    """The budget section ``data[section]`` covering ``phases``: its keys checked, every task of those phases capped, the
    task caps not above the phase cap (in decimal)."""
    keys = ("closed", "phase_cap_gpu_h", "task_cap_gpu_h") if section == _FIRST_BUDGET else \
        ("phases", "closed", "phase_cap_gpu_h", "task_cap_gpu_h")
    table = _table(data, section, section, keys, "key")
    tasks = tuple(task for phase in phases for task in TASK_IDS[phase])
    raw_caps = table["task_cap_gpu_h"]
    unquoted = isinstance(raw_caps, dict) and any(isinstance(value, dict) for value in raw_caps.values())
    example = tasks[0] if tasks else "L<phase>.<n>"
    hint = (f'; write task IDs in quotes, as "{example}" = 0.0: without the quotes TOML reads the dot as a table '
            f"inside a table") if unquoted else ""
    caps = _table(table, "task_cap_gpu_h", f"{section}.task_cap_gpu_h", tasks, "task ID", hint)
    budget = BudgetCfg(
        section=section, phases=phases, closed=_typed(table["closed"], bool, f"{section}.closed"),
        phase_cap_gpu_h=_cap_gpu_h(table["phase_cap_gpu_h"], f"{section}.phase_cap_gpu_h"),
        task_cap_gpu_h=tuple((task, _cap_gpu_h(caps[task], f'{section}.task_cap_gpu_h."{task}"')) for task in tasks))
    if _decimal_sum(cap for _, cap in budget.task_cap_gpu_h) > _decimal(budget.phase_cap_gpu_h):
        raise ValueError(f"the task caps add up to {budget.task_caps_total_gpu_h()!r} GPU-hours, more than the phase "
                         f"cap {section}.phase_cap_gpu_h = {budget.phase_cap_gpu_h!r} (added and compared in decimal)")
    return budget


def _later_phases(data: dict[str, Any], section: str, taken: set[str]) -> tuple[str, ...]:
    """The ``phases`` of a later budget section: a list of known phases, none in another section, spelled by the name."""
    if not isinstance(data[section], dict):
        raise ValueError(f"[{section}] must be a table, got {data[section]!r}")
    if "phases" not in data[section]:
        raise ValueError(f"missing key(s) in [{section}]: ['phases']")
    listed = data[section]["phases"]
    if type(listed) is not list or not listed:
        raise ValueError(f"{section}.phases must be a list of at least one phase, as [\"L1\", \"L2\"], got {listed!r}")
    phases = tuple(_typed(phase, str, f"{section}.phases") for phase in listed)
    for phase in phases:
        if phase not in TASK_IDS:
            raise ValueError(f"[{section}]: phase {phase!r} is not a known phase (known: {list(TASK_IDS)})")
        if phase in taken or phases.count(phase) > 1:
            raise ValueError(f"[{section}]: phase {phase} is in two budget sections (or twice in one); a phase has one cap")
        taken.add(phase)
    expected = _LATER_BUDGET + "_".join(phase.lower() for phase in phases)
    if section != expected:
        raise ValueError(f"[{section}]: the section's name must spell its phases {list(phases)}: expected [{expected}]")
    return phases


def load_ste_learning(path: str | Path = SETTINGS_FILE) -> tuple[SteLearningCfg, Provenance]:
    """Load the track's settings file. Returns the settings and where they came from (path, sha256 of the bytes read).

    Raises ``ValueError`` for a file that is not UTF-8 text or not valid TOML (the message names the file), an unknown
    or missing section, key or task ID, a value of the wrong type, an unknown phase, a phase in work that no budget
    section covers or that is in a closed section, a later budget section whose phases are unknown, taken or not
    spelled by its name, a cap that is negative or not finite, or task caps that add up (in decimal) to more than their section's phase cap.
    """
    path = Path(path)
    raw = path.read_bytes()
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as err:
        raise ValueError(f"{path}: not UTF-8 text ({err})") from err
    except tomllib.TOMLDecodeError as err:
        raise ValueError(f"{path}: not valid TOML ({err})") from err
    later = tuple(name for name in data if name.startswith(_LATER_BUDGET))
    _exact(data, ("track", _FIRST_BUDGET, *later), "section", path.name)

    track_table = _table(data, "track", "track", ("plan_version", "phase"), "key")
    track = TrackCfg(plan_version=_typed(track_table["plan_version"], int, "track.plan_version"),
                     phase=_typed(track_table["phase"], str, "track.phase"))
    if track.plan_version < 1:
        raise ValueError(f"track.plan_version must be 1 or more, got {track.plan_version}")
    if track.phase not in TASK_IDS:
        raise ValueError(f"track.phase must be one of {list(TASK_IDS)}, got {track.phase!r}")

    budget = _budget(data, _FIRST_BUDGET, BUDGET_PHASES)
    taken = set(BUDGET_PHASES)
    later_budgets = tuple(_budget(data, section, _later_phases(data, section, taken)) for section in later)
    cfg = SteLearningCfg(track=track, budget=budget, later_budgets=later_budgets)
    if not any(track.phase in each.phases for each in cfg.budgets()):
        raise ValueError(f"the phase in work, track.phase = {track.phase!r}, has no budget section (add "
                         f"[{_LATER_BUDGET}{track.phase.lower()}] or a section whose phases include it)")
    if cfg.budget_in_work().closed:
        raise ValueError(f"the phase in work, track.phase = {track.phase!r}, is in [{cfg.budget_in_work().section}], "
                         f"which is closed: a closed phase cannot be in work")
    return cfg, Provenance(str(path), hashlib.sha256(raw).hexdigest())
