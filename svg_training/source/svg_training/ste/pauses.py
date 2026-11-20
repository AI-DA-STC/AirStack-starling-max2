"""Paused time of the GPU jobs, for every cap and GPU-hour count of the STE learning track (task L0.7). Linux only.

The owner pauses the jobs to use the PC (``scripts/gpu_pause.sh pause`` = SIGSTOP, ``resume`` = SIGCONT). A paused
interval is neither GPU time nor wall clock against a cap. The pause may be made with any copy of the script:

* a copy from task L0.7 on appends the event line to the ONE shared log (``ste/shared.py``: ``pauses.log`` in the
  shared folder) and, the same text, to the legacy log of its own worktree;
* an older copy in another worktree appends only to ``<that worktree>/svg_training/runs/nus_port/phase5/pauses.log``.

So the reader takes the shared log and the legacy log of every worktree (:func:`pause_logs`), merges their EVENTS,
counts an event found in two logs once, and only then pairs pauses with resumes. Merging events, not intervals, lets a
pause made by one copy be closed by a resume made by another.

The interval arithmetic is ``nus/pauses.py``'s own, imported, not copied (``paused_intervals``, ``effective_seconds``):
its functions take the path of a log, so the merged log is kept in a file without a name (``tempfile.TemporaryFile``
in the shared folder, reached by its ``/proc/self/fd/<n>`` path; it leaves no file behind and goes with the process)
and handed to them. The merged log is rebuilt only when a log's size or modification time changes, so a trainer may
ask at every step.

One rule is added before the hand-over. A pause that was still open when the machine went down (a power cut during an
owner pause) ended at the latest when the machine came back: nothing is paused after a boot. Without it that pause
would run to "now" for ever and no cap would fire again. A resume at the boot time, marked ``"synthetic": true``, is
therefore merged in when the events before this boot end inside a pause. Only the current boot is known; an older
boot in the middle of the log is not corrected.

**A pause counts only for the jobs it stopped** (L07-C1). ``gpu_pause.sh`` writes, in every pause line, the pids of
the processes it stopped (``"pids": [...]``; ``[]`` when it found none: then the pause is only the owner's "I am using
this PC"). A job's time is reduced by a pause only if one of the job's own pids is in that list: the trainer's own pid
(``ste/run_contract.py``), the command's pid of the job record (``ste/jobs.py``), or the pids of a ledger line
(``ste/budget.py``). The pause lines are filtered per job BEFORE they are paired with resumes (the pairing ignores a
pause while one is open, so a filter after it would miss a job stopped by the second of two pauses); every resume and
stop is kept, because the script sends SIGCONT to every job it finds. A pause line with no ``"pids"`` list at all (no
committed copy of the script ever wrote one; a hand-written or foreign line) counts for every job, as before. The
owner's view, every pause whoever it stopped, is :func:`paused_intervals` without ``pids`` and :func:`open_pause`
(``ste/jobs.py`` refuses a launch while a pause is open).

A line that is not a JSON event (a line torn by a power cut) is skipped and reported on stderr. Standard library only.
"""
from __future__ import annotations

import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import IO, Iterable

from ..nus import pauses as nus_pauses              # standard library only: no PyTorch, no Isaac
from . import shared

_PROC_STAT = Path("/proc/stat")
_BOOT_KEY = "btime"                                 # "btime <unix seconds>": when this boot started
_FD_FOLDER = Path("/proc/self/fd")
_PAUSE = "pause"
_CLOSING = ("resume", "stop")

_merged: dict[tuple[Path, ...], tuple[tuple, IO[bytes]]] = {}   # logs -> (how they looked when merged, nameless file)
_one_job: dict[tuple[Path, ...], tuple[tuple, IO[bytes]]] = {}  # logs -> ((merged as, pids), that job's nameless file)
_counts = {"merges": 0}


def boot_time_s() -> float:
    """Unix time at which this boot started (``btime`` of ``/proc/stat``)."""
    for line in _PROC_STAT.read_text().splitlines():
        key, _, value = line.partition(" ")
        if key == _BOOT_KEY:
            return float(value)
    raise RuntimeError(f"no {_BOOT_KEY} line in {_PROC_STAT}")


def pause_logs() -> tuple[Path, ...]:
    """The shared pause log, then the legacy log of every worktree (files that do not exist are read as empty)."""
    return (shared.pauses_log(), *shared.legacy_pause_logs())


def _signature(logs: tuple[Path, ...], boot_s: float) -> tuple:
    seen = []
    for log in logs:
        try:
            status = log.stat()
            seen.append((status.st_mtime_ns, status.st_size))
        except FileNotFoundError:
            seen.append(None)
    return (boot_s, *seen)


def _read_events(logs: tuple[Path, ...]) -> list[dict]:
    """Every event of ``logs``, an event found in more than one log once, oldest first."""
    rows: dict[str, dict] = {}
    unreadable = 0
    for log in logs:
        try:
            text = log.read_text()
        except FileNotFoundError:
            continue
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                usable = isinstance(row["event"], str) and type(row["time"]) in (int, float) and math.isfinite(row["time"])
            except (ValueError, KeyError, TypeError):
                usable = False
            if usable:
                rows.setdefault(json.dumps(row, sort_keys=True), row)
            else:
                unreadable += 1
    if unreadable:
        print(f"[ste pauses] {unreadable} unreadable line(s) skipped in the pause logs "
              f"{[str(log) for log in logs if log.exists()]}", file=sys.stderr)
    return sorted(rows.values(), key=lambda row: row["time"])


def _path(nameless: IO[bytes]) -> Path:
    return _FD_FOLDER / str(nameless.fileno())


def _store(nameless: IO[bytes], events: list[dict]) -> Path:
    data = "".join(json.dumps(event) + "\n" for event in events).encode()
    os.ftruncate(nameless.fileno(), 0)
    os.pwrite(nameless.fileno(), data, 0)
    return _path(nameless)


def _default(logs: Iterable[Path | str] | None) -> tuple[Path, ...]:
    return pause_logs() if logs is None else tuple(Path(log) for log in logs)


def merged_log(logs: Iterable[Path | str] | None = None) -> Path:
    """Path of the merged, de-duplicated pause log (a file without a name), in the line format of ``gpu_pause.sh``.

    ``logs``: the logs to merge; default :func:`pause_logs`. Rebuilt only when one of them changed since the last call.
    """
    logs = _default(logs)
    boot_s = boot_time_s()
    signature = _signature(logs, boot_s)
    kept = _merged.get(logs)
    if kept is not None and kept[0] == signature:
        return _path(kept[1])
    nameless = kept[1] if kept is not None else tempfile.TemporaryFile(dir=shared.shared_dir())
    events = _read_events(logs)
    before_boot = [event for event in events if event["time"] < boot_s]
    spans = nus_pauses.paused_intervals(_store(nameless, before_boot), now=math.inf)
    if spans and spans[-1][1] == math.inf:          # the machine went down inside a pause: it ended at the boot
        resume = {"event": _CLOSING[0], "time": boot_s, "pids": [], "by": "boot", "synthetic": True}
        events = sorted([*events, resume], key=lambda row: row["time"])
    path = _store(nameless, events)
    _merged[logs] = (signature, nameless)
    _counts["merges"] += 1
    return path


def stopped(event: dict, pids: frozenset[int]) -> bool:
    """Whether the pause ``event`` stopped a process of ``pids`` (a job's own pids). A line without a ``"pids"`` list
    counts for every job (the rule before L07-C1)."""
    listed = event.get("pids")
    if not isinstance(listed, list):
        return True
    return any(type(pid) is int and pid in pids for pid in listed)


def job_log(pids: Iterable[int], logs: Iterable[Path | str] | None = None) -> Path:
    """Path of the merged pause log as one job sees it (a file without a name): the pauses that stopped one of
    ``pids``, every resume and stop. One such file per set of logs, rewritten when the job or a log changes."""
    logs, pids = _default(logs), frozenset(pids)
    merged = merged_log(logs)
    key = (_merged[logs][0], pids)
    kept = _one_job.get(logs)
    if kept is not None and kept[0] == key:
        return _path(kept[1])
    nameless = kept[1] if kept is not None else tempfile.TemporaryFile(dir=shared.shared_dir())
    events = [json.loads(line) for line in merged.read_text().splitlines()]
    path = _store(nameless, [event for event in events if event["event"] != _PAUSE or stopped(event, pids)])
    _one_job[logs] = (key, nameless)
    return path


def merges_done() -> int:
    """How many times this process has rebuilt a merged log (tests: a read with nothing changed rebuilds nothing)."""
    return _counts["merges"]


def pause_events(logs: Iterable[Path | str] | None = None) -> list[dict]:
    """The merged events, oldest first: ``{"event": "pause" | "resume" | "stop", "time": <unix s>, ...}``."""
    return [json.loads(line) for line in merged_log(logs).read_text().splitlines()]


def open_pause(logs: Iterable[Path | str] | None = None) -> dict | None:
    """The pause event that opened a pause still open now, whoever it stopped (none, or one closed by a later resume,
    a stop or a boot: None). Pairing as ``nus/pauses.py``: after the last resume or stop, the first pause opens."""
    spans = nus_pauses.paused_intervals(merged_log(logs), now=math.inf)
    if not spans or spans[-1][1] != math.inf:
        return None
    opener = None
    for event in pause_events(logs):
        if event["event"] in _CLOSING:
            opener = None
        elif event["event"] == _PAUSE and opener is None:
            opener = event
    return opener


def paused_intervals(now: float | None = None, logs: Iterable[Path | str] | None = None,
                     pids: Iterable[int] | None = None) -> list[tuple[float, float]]:
    """(start, end) in unix seconds of every paused interval; a pause still open ends at ``now`` (default: the clock).
    ``pids``: only the pauses that stopped one of these (a job's own pids); default every pause (the owner's view)."""
    return nus_pauses.paused_intervals(merged_log(logs) if pids is None else job_log(pids, logs), now=now)


def effective_seconds(start: float, end: float, pids: Iterable[int], logs: Iterable[Path | str] | None = None) -> float:
    """Wall clock from ``start`` to ``end`` (unix seconds) less the time a pause had stopped the job whose own pids are
    ``pids``: the time every cap uses. ``pids`` has no default: a pause that did not stop the job takes nothing off."""
    return nus_pauses.effective_seconds(start, end, job_log(pids, logs))


def paused_seconds(start: float, end: float, pids: Iterable[int], logs: Iterable[Path | str] | None = None) -> float:
    """The time inside ``start`` to ``end``, in seconds, that a pause had stopped the job whose own pids are ``pids``."""
    return (end - start) - effective_seconds(start, end, pids, logs)
