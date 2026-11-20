"""The live state file of the STE learning track: ``<shared folder>/state.json`` (task L0.7). Linux only.

One file, the same from every worktree (``ste/shared.py``), git-ignored: which jobs were launched, whether each is
still alive, and the state of each task. It is live process state, so it is not kept in the tracked
``ste_learning/status/`` folder (lead's call, 20 Nov 2026; AUTOMATION section 1 first proposed that path).

Writing. Every write goes through :func:`update`: an exclusive ``flock`` on ``state.lock``, the file read again under
the lock, the change applied, the result checked, then written whole (``ste/atomic.py``: temporary file in the same
folder, sync, rename). Two processes updating at once lose no update; a process killed mid-write leaves the old file.
A file that does not parse, or whose ``schema`` is not :data:`SCHEMA`, raises :class:`StateError` and is never
overwritten.

The file (schema 1; AUTOMATION section 1 trimmed to what phase L0 needs, so no ``session``, ``gpu``, ``budgets`` or
``gates_open`` block: budgets are computed from the ledger by ``ste/budget.py``, not stored here)::

    {"schema": 1,                 version of this layout; any other value raises on read
     "updated": "<ISO time>",     UTC time of the last write (null before the first)
     "boot_id": "<boot id>",      kernel boot id of the last writer (null before the first)
     "phase": "L0",               phase in work, as [track] phase of configs/ste_learning.toml (null until a launch)
     "tasks": {"<task ID>": {     one entry per task the lead or the orchestrator has touched
         "state": "<word>",       one of TASK_STATES (AUTOMATION section 1: queued, building, ... failed)
         "attempts": 0}},         launches that counted as attempts (a relaunch after a reboot is not one)
     "jobs": {"<job name>": {     one entry per job name; a relaunch under the same name replaces it
         "task": "L0.11",         the task the job belongs to
         "pid": 123,              pid of the job's wrapper (scripts/ste_job.py _run): session leader of the job
         "pid_start": 456,        that process's start time, clock ticks since boot (field 22 of /proc/<pid>/stat)
         "boot_id": "<boot id>",  kernel boot id at launch
         "cmd": ["python", ...],  the exact command, one list item per argument
         "cwd": "<folder>",       the folder the command runs in
         "run_dir": "<folder>",   the run folder (job.json, cmd.txt, exit_code, heartbeat, launches.jsonl)
         "log": "<file>",         where the command's output goes (appended at a relaunch)
         "started": 1.0,          unix time of the launch, seconds
         "expected_min_s": 60.0,  the shortest effective duration a real finish can have, seconds
         "gpu_h": 0.0,            GPU-hours asked for at launch; 0 for a CPU job (it then logs no GPU time)
         "launch": 1,             1 for the first launch of this run folder, 2 for the first relaunch, ...
         "child_pid": 124,        pid of the command itself, set by the wrapper (null until it has started)
         "child_start": 457,      the command's start time, clock ticks since boot (null with child_pid)
         "exit_code": null,       the command's own exit code, set by the wrapper when it ends (null while it runs)
         "ended": null}}}         unix time at which the command ended (null while it runs)

Is a job alive? Never by name or command line (a watcher that searched command lines once matched itself and never
fired). A recorded process is alive only if (1) the record's boot id is this boot's, (2) the pid exists and is not a
zombie, and (3) that process's start time equals the recorded one. A pid reused by another program fails (3); a record
left by a power cut fails (1) and reads "dead (previous boot)". A job is alive while its wrapper or its command passes
the test. Standard library only.
"""
from __future__ import annotations

import contextlib
import datetime
import fcntl
import json
from pathlib import Path
from typing import Any, Callable, Iterator

from . import atomic, shared

SCHEMA = 1
TASK_STATES = ("queued", "building", "testing", "gate-written", "running", "scoring", "recorded", "documented",
               "merged", "paused", "blocked-on-human", "failed")
ALIVE = "alive"
ALIVE_NO_WRAPPER = "alive (wrapper gone)"     # the command still runs but nothing will record its exit code
DEAD = "dead"
DEAD_PREVIOUS_BOOT = "dead (previous boot)"

_TOP_KEYS = ("schema", "updated", "boot_id", "phase", "tasks", "jobs")
_TASK_KEYS = ("state", "attempts")
_NUMBER = (int, float)
_JOB_KINDS: dict[str, tuple[type, ...]] = {        # key -> the types its value may have (bool is never a number here)
    "task": (str,), "pid": (int,), "pid_start": (int,), "boot_id": (str,), "cmd": (list,), "cwd": (str,),
    "run_dir": (str,), "log": (str,), "started": _NUMBER, "expected_min_s": _NUMBER, "gpu_h": _NUMBER,
    "launch": (int,), "child_pid": (int, type(None)), "child_start": (int, type(None)),
    "exit_code": (int, type(None)), "ended": (*_NUMBER, type(None)),
}
JOB_KEYS = tuple(_JOB_KINDS)

_BOOT_ID_FILE = Path("/proc/sys/kernel/random/boot_id")
_PROC = Path("/proc")
_STAT_STATE_FIELD = 3                     # /proc/<pid>/stat, fields counted from 1 as in proc(5): 3 = state letter
_STAT_START_FIELD = 22                    # 22 = starttime, clock ticks since boot
_NOT_RUNNING = ("Z", "X")                 # zombie (dead, not yet collected by its parent), dead


class StateError(ValueError):
    """``state.json`` is malformed, has an unknown schema version, or a change would make it so."""


# ------------------------------------------------------------------------------------------------ processes
def boot_id() -> str:
    """The kernel's id of this boot: a new random value at every boot."""
    return _BOOT_ID_FILE.read_text().strip()


def parse_stat(line: str) -> tuple[str, int]:
    """(state letter, start time in clock ticks since boot) from the text of ``/proc/<pid>/stat``. The program name
    (field 2) is in brackets and may itself hold brackets and spaces, so fields are counted after the LAST ``)``."""
    fields = line.rsplit(")", 1)[1].split()
    return fields[0], int(fields[_STAT_START_FIELD - _STAT_STATE_FIELD])


def _stat(pid: int) -> tuple[str, int] | None:
    try:
        return parse_stat((_PROC / str(pid) / "stat").read_text())
    except (FileNotFoundError, ProcessLookupError):
        return None


def process_state(pid: int) -> str | None:
    """The state letter of a process (``R`` running, ``S`` sleeping, ``T`` stopped = paused, ``Z`` zombie), or None
    when there is no such process."""
    found = _stat(pid)
    return None if found is None else found[0]


def process_start_time(pid: int) -> int | None:
    """Start time of the live process ``pid`` in clock ticks since boot; None when there is no such process or it is a
    zombie (ended, only not yet collected by its parent)."""
    found = _stat(pid)
    return None if found is None or found[0] in _NOT_RUNNING else found[1]


def _same_process(pid: int | None, started: int | None) -> bool:
    return pid is not None and started is not None and process_start_time(pid) == started


def job_status(job: dict[str, Any]) -> str:
    """:data:`ALIVE`, :data:`ALIVE_NO_WRAPPER`, :data:`DEAD` or :data:`DEAD_PREVIOUS_BOOT` for one job record."""
    if job["boot_id"] != boot_id():
        return DEAD_PREVIOUS_BOOT
    if _same_process(job["pid"], job["pid_start"]):
        return ALIVE
    if _same_process(job["child_pid"], job["child_start"]):
        return ALIVE_NO_WRAPPER
    return DEAD


def job_alive(job: dict[str, Any]) -> bool:
    """True only if the job's wrapper, or its command, exists with the recorded start time, in the recorded boot."""
    return job_status(job) in (ALIVE, ALIVE_NO_WRAPPER)


# ------------------------------------------------------------------------------------------------ the file
def new_state() -> dict[str, Any]:
    """The state before anything was written."""
    return {"schema": SCHEMA, "updated": None, "boot_id": None, "phase": None, "tasks": {}, "jobs": {}}


def _exact_keys(table: Any, keys: tuple[str, ...], where: str) -> None:
    if not isinstance(table, dict):
        raise StateError(f"{where} must be a JSON object, got {table!r}")
    unknown, missing = sorted(set(table) - set(keys)), [key for key in keys if key not in table]
    if unknown or missing:
        raise StateError(f"{where}: unknown key(s) {unknown}, missing key(s) {missing} (known: {list(keys)})")


def validate(data: Any) -> dict[str, Any]:
    """``data`` if it is a well-formed state of this schema; :class:`StateError` otherwise."""
    if not isinstance(data, dict):
        raise StateError(f"state.json must be a JSON object, got {type(data).__name__}")
    if data.get("schema") != SCHEMA or type(data.get("schema")) is not int:
        raise StateError(f"state.json has schema version {data.get('schema')!r}; this code reads version {SCHEMA} only")
    _exact_keys(data, _TOP_KEYS, "state.json")
    for key in ("updated", "boot_id", "phase"):
        if data[key] is not None and not isinstance(data[key], str):
            raise StateError(f"state.json: {key} must be text or null, got {data[key]!r}")
    for key in ("tasks", "jobs"):
        if not isinstance(data[key], dict):
            raise StateError(f"state.json: {key} must be a JSON object, got {data[key]!r}")
    for task_id, task in data["tasks"].items():
        _exact_keys(task, _TASK_KEYS, f"task {task_id!r}")
        if task["state"] not in TASK_STATES:
            raise StateError(f"task {task_id!r}: state {task['state']!r} is not one of {list(TASK_STATES)}")
        if type(task["attempts"]) is not int or task["attempts"] < 0:
            raise StateError(f"task {task_id!r}: attempts must be a whole number, 0 or more, got {task['attempts']!r}")
    for name, job in data["jobs"].items():
        _exact_keys(job, JOB_KEYS, f"job {name!r}")
        for key, kinds in _JOB_KINDS.items():
            if type(job[key]) not in kinds:
                raise StateError(f"job {name!r}: {key} must be {' or '.join(kind.__name__ for kind in kinds)}, "
                                 f"got {job[key]!r}")
        if not all(isinstance(part, str) for part in job["cmd"]):
            raise StateError(f"job {name!r}: cmd must be a list of texts, got {job['cmd']!r}")
    return data


def read() -> dict[str, Any]:
    """The state on disk, checked; a fresh empty state when the file does not exist yet (nothing is created)."""
    path = shared.shared_dir(create=False) / shared.STATE_NAME
    try:
        text = path.read_text()
    except FileNotFoundError:
        return new_state()
    try:
        data = json.loads(text)
    except ValueError as err:
        raise StateError(f"{path}: not valid JSON ({err})") from err
    return validate(data)


@contextlib.contextmanager
def locked() -> Iterator[None]:
    """Hold the exclusive lock of ``state.json`` (blocks while another process holds it; freed if this one dies)."""
    with open(shared.state_lock(), "a") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield


def update(change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """Apply ``change`` to the state under the lock and write it. ``change`` gets the state as read under the lock and
    alters it in place; if it raises, or leaves a malformed state, nothing is written. Returns the state as written."""
    with locked():
        data = read()
        change(data)
        data["updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        data["boot_id"] = boot_id()
        validate(data)
        atomic.write_text(shared.state_file(), json.dumps(data, indent=1) + "\n")
    return data
