"""Settings of STE's learning track: typed, frozen, TOML only (``configs/ste_learning.toml``).

Task L0.1 holds the track's process settings: which plan and phase, and the GPU-hour caps of the phase in work. Game
settings arrive with the tasks that build them (``configs/ste_game.toml``, task L0.8 onwards), not here.

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
from pathlib import Path
from typing import Any

from ..core.game_config import CONFIGS  # standard library only: no PyTorch, no Isaac

SETTINGS_FILE = CONFIGS / "ste_learning.toml"

# Task IDs of each phase the loader knows, in the order of the table in ste_learning/PLAN.md section 4. Names, not
# numbers; tests/test_ste_config.py reads the IDs out of PLAN.md and fails if this tuple or the file differs from it.
TASK_IDS: dict[str, tuple[str, ...]] = {
    "L0": ("L0.1", "L0.7", "L0.8", "L0.9", "L0.10", "L0.11", "L0.12", "L0.2", "L0.13", "L0.3", "L0.4", "L0.5", "L0.6"),
}


@dataclass(frozen=True)
class TrackCfg:
    """Which plan the settings belong to: the version of ste_learning/PLAN.md and the phase in work (a TASK_IDS key)."""
    plan_version: int
    phase: str


@dataclass(frozen=True)
class BudgetCfg:
    """GPU-hour caps of the phase in work.

    ``phase_cap_gpu_h``: the most GPU-hours the whole phase may use. ``task_cap_gpu_h``: one (task ID, cap in GPU-hours)
    pair per task of the phase, in the plan's order; a tuple of pairs, so nothing in it can be changed after loading.
    The loader has checked that no cap is negative and that the task caps together do not exceed the phase cap.
    """
    phase_cap_gpu_h: float
    task_cap_gpu_h: tuple[tuple[str, float], ...]

    def cap_gpu_h(self, task_id: str) -> float:
        """The cap of one task in GPU-hours; ``KeyError`` for a task that is not in the phase."""
        for task, cap in self.task_cap_gpu_h:
            if task == task_id:
                return cap
        raise KeyError(f"no GPU-hour cap for task {task_id!r} (known: {[task for task, _ in self.task_cap_gpu_h]})")

    def task_caps_total_gpu_h(self) -> float:
        """The task caps added up, in GPU-hours."""
        return math.fsum(cap for _, cap in self.task_cap_gpu_h)


@dataclass(frozen=True)
class SteLearningCfg:
    track: TrackCfg
    budget: BudgetCfg


@dataclass(frozen=True)
class Provenance:
    """Where the settings came from: the file's path and the sha256 of its bytes (comments included)."""
    settings_file: str
    settings_sha256: str


_KINDS = {int: "a whole number", float: "a decimal number (write 3.0, not 3)", str: "text in quotes"}


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


def _table(parent: dict[str, Any], name: str, where: str, keys: tuple[str, ...], what: str) -> dict[str, Any]:
    """The table ``parent[name]`` once its keys are checked to be exactly ``keys``; ``what`` names a key in messages."""
    table = parent[name]
    if not isinstance(table, dict):
        raise ValueError(f"[{where}] must be a table, got {table!r}")
    _exact(table, keys, what, f"[{where}]")
    return table


def _exact(table: dict[str, Any], keys: tuple[str, ...], what: str, where: str) -> None:
    unknown = sorted(set(table) - set(keys))
    if unknown:
        raise ValueError(f"unknown {what}(s) in {where}: {unknown} (known: {list(keys)})")
    missing = [key for key in keys if key not in table]
    if missing:
        raise ValueError(f"missing {what}(s) in {where}: {missing}")


def load_ste_learning(path: str | Path = SETTINGS_FILE) -> tuple[SteLearningCfg, Provenance]:
    """Load the track's settings file. Returns the settings and where they came from (path, sha256 of the bytes read).

    Raises ``ValueError`` for an unknown or missing section, key or task ID, a value of the wrong type, an unknown
    phase, a cap that is negative or not finite, or task caps that add up to more than the phase cap.
    """
    path = Path(path)
    raw = path.read_bytes()
    data = tomllib.loads(raw.decode())
    _exact(data, ("track", "budget"), "section", path.name)

    track_table = _table(data, "track", "track", ("plan_version", "phase"), "key")
    track = TrackCfg(plan_version=_typed(track_table["plan_version"], int, "track.plan_version"),
                     phase=_typed(track_table["phase"], str, "track.phase"))
    if track.plan_version < 1:
        raise ValueError(f"track.plan_version must be 1 or more, got {track.plan_version}")
    if track.phase not in TASK_IDS:
        raise ValueError(f"track.phase must be one of {list(TASK_IDS)}, got {track.phase!r}")

    budget_table = _table(data, "budget", "budget", ("phase_cap_gpu_h", "task_cap_gpu_h"), "key")
    tasks = TASK_IDS[track.phase]
    caps = _table(budget_table, "task_cap_gpu_h", "budget.task_cap_gpu_h", tasks, "task ID")
    budget = BudgetCfg(
        phase_cap_gpu_h=_cap_gpu_h(budget_table["phase_cap_gpu_h"], "budget.phase_cap_gpu_h"),
        task_cap_gpu_h=tuple((task, _cap_gpu_h(caps[task], f'budget.task_cap_gpu_h."{task}"')) for task in tasks))
    if budget.task_caps_total_gpu_h() > budget.phase_cap_gpu_h:
        raise ValueError(f"the task caps add up to {budget.task_caps_total_gpu_h()} GPU-hours, more than the phase cap "
                         f"budget.phase_cap_gpu_h = {budget.phase_cap_gpu_h}")
    return SteLearningCfg(track=track, budget=budget), Provenance(str(path), hashlib.sha256(raw).hexdigest())
