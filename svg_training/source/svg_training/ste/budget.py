"""The GPU-hour ledger of the STE learning track and the check made before a launch (task L0.7). Linux only.

The ledger is ``gpu_hours.log`` in the shared folder (``ste/shared.py``), append-only, one JSON line per CUDA interval
of a job, in the line format of the NUS port's ``gpu_hours.log`` so that the same arithmetic reads it::

    {"group": "<task ID>", "job": "<job name>", "device": "cuda", "start": <unix s>, "end": <unix s>, "pids": [<pid>]}

A job's wrapper (``ste/jobs.py``) appends one line per beat while the job runs, each from the end of the last, and
one when it ends, with the pid of the job's command. So a job that is still running is counted up to its last beat,
and a power cut loses at most one beat. A CPU job logs nothing.

GPU-hours used, of a task or of a phase, are the union of the intervals (jobs side by side count once) less the
paused time inside them. A pause counts for a line only if it stopped one of the line's pids (L07-C1, ``ste/pauses.py``):
each line first loses the time its own job was paused, and only then are the lines united, so a paused job does not
take time off a sibling that ran on. A line without ``"pids"`` (written before L07-C1) loses every pause, as it did
then. The union is ``nus/pauses.py::logged_gpu_hours``, imported, not copied: the unpaused pieces are handed to it in a
file without a name. A line that is not a ledger line (torn by a power cut) is skipped and reported on stderr.

:func:`check_launch` compares used plus asked with the caps of ``configs/ste_learning.toml`` (the task's cap and the
phase cap) and raises :class:`BudgetError` naming the cap, what is used and what was asked. The hours a job asks for
are its total over all its launches: at a relaunch the hours it has already logged count as part of that, so the same
launch line resumes a job. Because used hours are a union, checking every launch this way keeps the union under the
cap as long as each job stops at the hours it asked for (its own cap, ``ste/run_contract.py``). Standard library only.
"""
from __future__ import annotations

import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Iterable, NamedTuple

from ..nus import pauses as nus_pauses              # standard library only: no PyTorch, no Isaac
from . import pauses, shared
from .config import SETTINGS_FILE, TASK_IDS, load_ste_learning

CUDA = "cuda"                                       # a device name that starts with this used the GPU
_ONE_GROUP = "selected"
_FD_FOLDER = Path("/proc/self/fd")
_ROUNDING_GPU_H = 1e-9                              # 0.1 + 0.2 is 0.30000000000000004 in binary; a cap of 0.3 still fits


class BudgetError(ValueError):
    """A launch would exceed a GPU-hour cap, or names a task or an amount the settings do not know."""


class Usage(NamedTuple):
    """Caps and GPU-hours used at a launch check, for the task and for its phase."""
    task_cap_gpu_h: float
    task_used_gpu_h: float
    phase_cap_gpu_h: float
    phase_used_gpu_h: float


def log_interval(task: str, job: str, device: str, start_s: float, end_s: float,
                 pids: Iterable[int] | None = None) -> bool:
    """Append one interval to the ledger if ``device`` is a CUDA device; a CPU job logs nothing. Returns whether a
    line was written. ``start_s``, ``end_s``: unix seconds, end not before start. ``pids``: the job's own pids (its
    command's), so that only a pause that stopped it takes time off; None writes a line without pids, which every
    pause takes time off (the rule before L07-C1)."""
    if not end_s >= start_s:
        raise ValueError(f"an interval must not end before it starts: start {start_s!r}, end {end_s!r}")
    if not str(device).startswith(CUDA):
        return False
    row = {"group": task, "job": job, "device": str(device), "start": float(start_s), "end": float(end_s)}
    if pids is not None:
        row["pids"] = sorted(int(pid) for pid in pids)
    nus_pauses.append_row(shared.gpu_hours_log(), row)
    return True


def _rows() -> list[dict]:
    """Every readable line of the ledger."""
    ledger = shared.shared_dir(create=False) / shared.GPU_HOURS_LOG_NAME
    try:
        lines = ledger.read_text().splitlines()
    except FileNotFoundError:
        return []
    rows, unreadable = [], 0
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            usable = (isinstance(row["group"], str) and isinstance(row["device"], str)
                      and math.isfinite(float(row["start"])) and math.isfinite(float(row["end"])))
        except (ValueError, KeyError, TypeError):
            usable = False
        if usable:
            rows.append(row)
        else:
            unreadable += 1
    if unreadable:
        print(f"[ste budget] {unreadable} unreadable line(s) skipped in {ledger}", file=sys.stderr)
    return rows


def _unpaused(start_s: float, end_s: float, paused: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """The pieces of ``start_s`` to ``end_s`` outside ``paused`` (sorted, merged intervals, as ``nus/pauses.py`` gives)."""
    pieces, at = [], start_s
    for paused_from, paused_to in paused:
        if paused_to <= at or paused_from >= end_s:
            continue
        if paused_from > at:
            pieces.append((at, paused_from))
        at = paused_to
    if at < end_s:
        pieces.append((at, end_s))
    return pieces


def _pids_of(row: dict) -> frozenset[int] | None:
    """The job's own pids of a ledger line; None for a line without them (every pause counts for it)."""
    listed = row.get("pids")
    return frozenset(pid for pid in listed if type(pid) is int) if isinstance(listed, list) else None


def _gpu_h(tasks: tuple[str, ...], job: str | None = None) -> float:
    """GPU-hours of the ledger lines of ``tasks`` together (of one job only, if ``job`` is given): each CUDA interval
    less the time its own job was paused, then the union of what is left."""
    rows = [row for row in _rows() if row["group"] in tasks and (job is None or row.get("job") == job)
            and str(row["device"]).startswith(CUDA)]
    paused: dict[frozenset[int] | None, list[tuple[float, float]]] = {}
    pieces = []
    for row in rows:
        pids = _pids_of(row)
        if pids not in paused:
            paused[pids] = pauses.paused_intervals(pids=pids)
        pieces += [{"group": _ONE_GROUP, "device": CUDA, "start": start_s, "end": end_s}
                   for start_s, end_s in _unpaused(float(row["start"]), float(row["end"]), paused[pids])]
    if not pieces:
        return 0.0
    with tempfile.TemporaryFile(dir=shared.shared_dir()) as nameless:       # the NUS arithmetic takes a file
        nameless.write("".join(json.dumps(piece) + "\n" for piece in pieces).encode())
        nameless.flush()
        return nus_pauses.logged_gpu_hours(_FD_FOLDER / str(nameless.fileno()), _ONE_GROUP, os.devnull)


def task_gpu_h(task: str) -> float:
    """GPU-hours one task has used so far."""
    return _gpu_h((task,))


def job_gpu_h(task: str, job: str) -> float:
    """GPU-hours the job ``job`` of ``task`` has used so far, over all its launches."""
    return _gpu_h((task,), job)


def phase_gpu_h(phase: str) -> float:
    """GPU-hours a phase has used so far: the union over the tasks of ``TASK_IDS[phase]`` (``ste/config.py``)."""
    return _gpu_h(TASK_IDS[phase])


def check_launch(task: str, requested_gpu_h: float, settings: Path | str = SETTINGS_FILE, job: str | None = None) -> Usage:
    """Raise :class:`BudgetError` if launching a job of ``task`` that asks for ``requested_gpu_h`` GPU-hours would
    take the task past its cap or the phase past the phase cap (``settings``: the track's settings file). A CPU job
    asks for 0 and passes whenever its task exists. Returns the caps and what is used.

    ``requested_gpu_h`` is the job's total over all its launches. With ``job`` (the job's name) the hours that job has
    already logged are part of what it asked for, not a second request: only the rest is new. So the same launch line
    starts a job again after a power cut, and a job that has used up what it asked for adds nothing."""
    cfg, _ = load_ste_learning(settings)
    phase, name = cfg.track.phase, Path(settings).name
    if isinstance(requested_gpu_h, bool) or not isinstance(requested_gpu_h, (int, float)) \
            or not math.isfinite(requested_gpu_h) or requested_gpu_h < 0:
        raise BudgetError(f"asked must be a finite number of GPU-hours, 0 or more, got {requested_gpu_h!r}")
    try:
        task_cap = cfg.budget.cap_gpu_h(task)
    except KeyError:
        raise BudgetError(f"task {task} is not a task of phase {phase} in {name} "
                          f"(known: {[known for known, _ in cfg.budget.task_cap_gpu_h]})") from None
    usage = Usage(task_cap, task_gpu_h(task), cfg.budget.phase_cap_gpu_h, phase_gpu_h(phase))
    own = job_gpu_h(task, job) if job is not None else 0.0
    new = max(0.0, requested_gpu_h - own)
    mine = f" ({own:.3f} of them already used by job {job})" if own > 0 else ""
    for what, key, cap, used in ((f"task {task}", "budget.task_cap_gpu_h", usage.task_cap_gpu_h, usage.task_used_gpu_h),
                                 (f"phase {phase}", "budget.phase_cap_gpu_h", usage.phase_cap_gpu_h, usage.phase_used_gpu_h)):
        if new > 0 and used + new > cap + _ROUNDING_GPU_H:
            raise BudgetError(f"{what}: cap {cap!r} GPU-h ({key} in {name}), used {used:.3f}, asked {requested_gpu_h!r}"
                              f"{mine}: the launch could take it to {used + new:.3f} GPU-h, over the cap")
    return usage
