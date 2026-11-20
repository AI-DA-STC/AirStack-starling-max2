"""Launching a job detached, waiting for it, and listing jobs (STE learning track, task L0.7). Linux only.

The command line is ``scripts/ste_job.py`` (``launch``, ``wait``, ``status``); the logic is here so it can be tested.

**Launch.** The command is not started directly. The launcher starts a thin *wrapper* (``scripts/ste_job.py _run
<run folder>``) as the leader of a new session, detached from the launching terminal, with its output appended to
``<run folder>/job.log``. The wrapper starts the command, passes SIGINT and SIGTERM on to it, and when it ends writes
the command's own exit code to ``<run folder>/exit_code`` (atomically; 128 + n if signal n killed it) and into
``state.json``. The recorded pid is the wrapper's: signal it and the command gets the signal. The wrapper's command
line holds only the run folder, never the command, and the owner's ``gpu_pause.sh`` leaves ``scripts/ste_job.py``
processes alone: a paused or interrupted wrapper could not record the exit code.

The launcher holds the lock of ``state.json`` from before it starts the wrapper until the launch is recorded, and the
wrapper's first act is to take that lock: the command starts only once the record exists. A launch is refused
(:class:`LaunchRefused`) while an owner pause is open (``scripts/gpu_pause.sh pause`` with no ``resume`` yet, whether or
not it stopped a job: a pause is also the owner's "I am using this PC", and a job started during it would run
unpaused), while a job of the same name, or any job in the same run folder, is alive, and when ``ste/budget.py`` says
the hours asked for would pass the task's cap or the phase cap. The hours asked for are the
job's total over all its launches, so the hours it has already logged are not asked for a second time at a relaunch.

Files in the run folder: ``job.json`` (the launch record: the ``state.json`` fields of ``ste/state.py`` plus the job
name, the beat and a few environment variables), ``cmd.txt`` (the launch command line, to run again by hand),
``job.log``, ``exit_code`` (``exit_code.<n>`` once launch ``n`` has been followed by a relaunch), ``heartbeat``
(touched by the wrapper every beat: its modification time is when the job was last seen alive), ``launches.jsonl``
(one line per launch and per end). A GPU job (``gpu_h`` above 0) also gets one line per beat in the GPU-hour ledger.

**Wait.** Blocks until the job is no longer alive, by the test of ``ste/state.py`` (pid, start time, boot id, of the
wrapper or of the command); it never looks at process names or command lines, so a waiter whose own command line
names the job cannot match itself. Then one line::

    <task> <job> <VERDICT> exit=<code> duration=<s>s effective=<s>s

and its own exit status:

* the job's exit code, whatever it is (verdict DONE, CAP, NONFINITE, INTERRUPTED, REFUSED as ``ste/run_contract.py``
  names them, FAILED for any other code);
* **ENDED_EARLY** when the effective duration (wall clock less the owner's pauses that stopped the job's command) is
  under the expected minimum given
  at launch: status :data:`EXIT_ENDED_EARLY` if the job's code was 0 (a 0 that came too fast must not pass), else the
  job's own code;
* **DIED** when the job is gone and no exit code was recorded (killed with its wrapper, or lost with a previous
  boot): status :data:`EXIT_DIED`. The duration then runs to the job's last sign of life: the newest file of its
  run folder (the heartbeat, the log, a checkpoint).

A command the wrapper cannot start (a misspelt program) is recorded with exit code :data:`EXIT_NOT_STARTED`. If the
waiter itself fails (``state.json`` unreadable) its status is :data:`EXIT_TOOL_ERROR`, never one a job could return.

**Status.** One line per job of ``state.json``: alive, alive (paused), alive (wrapper gone), dead, or dead (previous
boot), with the exit code if one was recorded. Standard library only.
"""
from __future__ import annotations

import datetime
import json
import math
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, NamedTuple

from . import atomic, budget, pauses, shared, state
from .config import SETTINGS_FILE, load_ste_learning
from .run_contract import EXIT_DONE, EXIT_NAMES, EXIT_REFUSED

EXIT_ENDED_EARLY = 20        # waiter: the job exited 0 but in less than its expected minimum
EXIT_DIED = 21               # waiter: the job is gone and recorded no exit code
EXIT_NO_SUCH_JOB = 22        # waiter: state.json has no job of that name
EXIT_TOOL_ERROR = 23         # wait or status failed itself (an unreadable state.json): never a job's code
EXIT_NOT_STARTED = 127       # recorded for a command the wrapper could not start, as a shell reports "not found"
SIGNAL_EXIT_BASE = 128       # a command killed by signal n is recorded as 128 + n, as a shell reports it
POLL_S = 1.0                 # how often the waiter looks
BEAT_S = 60.0                # how often the wrapper touches the heartbeat and logs GPU time

DONE, FAILED, ENDED_EARLY, DIED = EXIT_NAMES[EXIT_DONE], "FAILED", "ENDED_EARLY", "DIED"
PAUSED = "alive (paused)"

WRAPPER_SCRIPT = shared.PACKAGE_DIR.parents[2] / "scripts" / "ste_job.py"
WRAPPER_COMMAND = "_run"
JOB_FILE, CMD_FILE, LOG_FILE, EXIT_FILE = "job.json", "cmd.txt", "job.log", "exit_code"
HEARTBEAT_FILE, LAUNCHES_FILE = "heartbeat", "launches.jsonl"
RECORDED_ENV = ("PYTHONPATH", "CUDA_VISIBLE_DEVICES", "PYTORCH_CUDA_ALLOC_CONF", shared.SHARED_ENV)
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_FORWARDED = (signal.SIGINT, signal.SIGTERM)
_STOPPED = "T"


class LaunchRefused(RuntimeError):
    """The launch was not made: the job is alive, the budget does not allow it, or an argument makes no sense."""


class NoSuchJob(KeyError):
    """``state.json`` has no job of that name."""


class Outcome(NamedTuple):
    """What the waiter found: the line it prints and its own exit status, with the parts they were made from."""
    line: str
    status: int
    verdict: str
    exit_code: int | None
    duration_s: float
    effective_s: float


def _append(path: Path, row: dict[str, Any]) -> None:
    with path.open("a") as stream:
        stream.write(json.dumps(row) + "\n")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None


def _start_ticks(pid: int) -> int:
    """Start time of a process this process has just started (it cannot be gone: nobody has collected it yet)."""
    return state.parse_stat(Path("/proc", str(pid), "stat").read_text())[1]


# ================================================================================================ launch
def launch(task: str, name: str, run_dir: Path | str, cmd: list[str], expected_min_s: float, gpu_h: float,
           settings: Path | str = SETTINGS_FILE, beat_s: float = BEAT_S, cwd: Path | str | None = None) -> dict[str, Any]:
    """Start ``cmd`` detached behind the wrapper and record the job. Returns its ``state.json`` record.

    ``task``: the task ID the job belongs to. ``name``: the job's name (letters, digits, ``.``, ``_``, ``-``).
    ``run_dir``: its run folder. ``expected_min_s``: the shortest effective duration, in seconds, a real finish can
    have (the waiter flags a shorter one). ``gpu_h``: GPU-hours asked for; 0 for a CPU job. ``settings``: the track's
    settings file (caps). ``beat_s``: seconds between heartbeats. ``cwd``: where the command runs (default: here).
    """
    if not _NAME.fullmatch(name):
        raise LaunchRefused(f"job name {name!r}: use letters, digits, '.', '_' and '-' only")
    if not cmd:
        raise LaunchRefused("no command to launch (put it after --)")
    if not (math.isfinite(expected_min_s) and expected_min_s >= 0):
        raise LaunchRefused(f"the expected minimum duration must be 0 or more seconds, got {expected_min_s!r}")
    if not (math.isfinite(beat_s) and beat_s > 0):
        raise LaunchRefused(f"the beat must be above 0 seconds, got {beat_s!r}")
    paused = pauses.open_pause()
    if paused is not None:
        made = datetime.datetime.fromtimestamp(paused["time"]).astimezone().isoformat(timespec="seconds")
        raise LaunchRefused(f"the owner's pause of {made} (by {paused.get('by', 'unknown')}, pids {paused.get('pids')}) "
                            f"is still open: nothing was launched. Only the owner ends it, with scripts/gpu_pause.sh "
                            f"resume; launch again after that")
    try:
        budget.check_launch(task, gpu_h, settings, job=name)
    except budget.BudgetError as err:
        raise LaunchRefused(str(err)) from err
    settings = Path(settings).resolve()
    phase = load_ste_learning(settings)[0].track.phase
    run_dir, cwd = Path(run_dir).resolve(), Path(cwd if cwd is not None else os.getcwd()).resolve()
    cmd = [str(part) for part in cmd]
    wrappers: list[subprocess.Popen] = []
    record: dict[str, Any] = {}

    def start_and_record(data: dict[str, Any]) -> None:
        for other, job in data["jobs"].items():
            same_folder = Path(job["run_dir"]) == run_dir
            if (other == name or same_folder) and state.job_alive(job):
                where = f" in the same run folder {run_dir}" if other != name else ""
                raise LaunchRefused(f"job {other!r} is {state.job_status(job)}{where} (pid {job['pid']}): "
                                    f"nothing was launched")
        run_dir.mkdir(parents=True, exist_ok=True)
        previous = _read_json(run_dir / JOB_FILE)
        number = previous["launch"] + 1 if previous is not None else 1
        if (run_dir / EXIT_FILE).exists():                       # the earlier launch's code: kept, under its number
            os.replace(run_dir / EXIT_FILE, run_dir / f"{EXIT_FILE}.{number - 1}")
        (run_dir / HEARTBEAT_FILE).unlink(missing_ok=True)
        log = run_dir / LOG_FILE
        started_s = time.time()
        with open(log, "ab") as out:
            wrapper = subprocess.Popen([sys.executable, str(WRAPPER_SCRIPT), WRAPPER_COMMAND, str(run_dir)], cwd=cwd,
                                       stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                       start_new_session=True)
        wrappers.append(wrapper)
        record.update({"task": task, "pid": wrapper.pid, "pid_start": _start_ticks(wrapper.pid),
                       "boot_id": state.boot_id(), "cmd": cmd, "cwd": str(cwd), "run_dir": str(run_dir),
                       "log": str(log), "started": started_s, "expected_min_s": float(expected_min_s),
                       "gpu_h": float(gpu_h), "launch": number, "child_pid": None, "child_start": None,
                       "exit_code": None, "ended": None})
        environment = {key: os.environ[key] for key in RECORDED_ENV if key in os.environ}
        atomic.write_text(run_dir / JOB_FILE, json.dumps(dict(record, name=name, beat_s=float(beat_s),
                                                              settings=str(settings), env=environment), indent=1) + "\n")
        again = [sys.executable, str(WRAPPER_SCRIPT), "launch", "--task", task, "--name", name, "--run-dir", str(run_dir),
                 "--min-s", repr(float(expected_min_s)), "--gpu-h", repr(float(gpu_h)), "--settings", str(settings),
                 "--beat-s", repr(float(beat_s)), "--", *cmd]
        atomic.write_text(run_dir / CMD_FILE, f"# launch {number} of job {name} (task {task}); environment: "
                                              f"{environment}\ncd {shlex.quote(str(cwd))} && {shlex.join(again)}\n")
        _append(run_dir / LAUNCHES_FILE, {"event": "launch", "launch": number, "time": started_s, "pid": wrapper.pid,
                                          "pid_start": record["pid_start"], "boot_id": record["boot_id"]})
        data["jobs"][name] = dict(record)
        data["phase"] = phase

    try:
        state.update(start_and_record)
    except BaseException:
        for wrapper in wrappers:                                 # started but not recorded: it must not run
            wrapper.kill()
        raise
    return record


# ================================================================================================ the wrapper
def _update_own_record(name: str, pid_start: int, **changes: Any) -> None:
    """Set fields of this wrapper's job in ``state.json``; a record that is no longer this wrapper's is left alone."""
    def change(data: dict[str, Any]) -> None:
        job = data["jobs"].get(name)
        if job is not None and (job["pid"], job["pid_start"], job["boot_id"]) == (os.getpid(), pid_start, state.boot_id()):
            job.update(changes)

    try:
        state.update(change)
    except state.StateError as err:                              # the exit_code file is the record that counts
        print(f"[ste job] state.json not updated ({err})", flush=True)


def run_wrapper(run_dir: Path | str) -> int:
    """The wrapper process (``scripts/ste_job.py _run <run folder>``): run the launch's command, pass SIGINT and
    SIGTERM on to it, beat while it runs, record its exit code when it ends."""
    run_dir = Path(run_dir)
    with state.locked():                                         # held by the launcher until the launch is recorded
        pass
    record = _read_json(run_dir / JOB_FILE)
    own_start = _start_ticks(os.getpid())
    if record is None or (record["pid"], record["pid_start"], record["boot_id"]) != (os.getpid(), own_start, state.boot_id()):
        print(f"[ste job] {run_dir / JOB_FILE} does not record this wrapper (pid {os.getpid()}): nothing is run",
              flush=True)
        return EXIT_REFUSED
    name, task, on_gpu = record["name"], record["task"], record["gpu_h"] > 0
    child: subprocess.Popen | None = None
    early: list[int] = []

    def pass_on(number: int, frame: Any) -> None:
        if child is None:
            early.append(number)
        else:
            child.send_signal(number)                            # does nothing once the command has ended

    def record_end(exit_code: int, ended_s: float, signal_name: str | None) -> None:
        atomic.write_text(run_dir / EXIT_FILE, f"{exit_code}\n")
        _append(run_dir / LAUNCHES_FILE, {"event": "end", "launch": record["launch"], "time": ended_s,
                                          "exit_code": exit_code, "signal": signal_name})
        _update_own_record(name, own_start, exit_code=exit_code, ended=ended_s)

    for number in _FORWARDED:
        signal.signal(number, pass_on)
    heartbeat = run_dir / HEARTBEAT_FILE
    heartbeat.touch()
    try:
        child = subprocess.Popen(record["cmd"], cwd=record["cwd"], stdin=subprocess.DEVNULL)
    except OSError as err:
        print(f"[ste job] the command could not be started ({err}): {record['cmd']}", flush=True)
        record_end(EXIT_NOT_STARTED, time.time(), None)
        return EXIT_DONE
    for number in early:
        child.send_signal(number)
    _update_own_record(name, own_start, child_pid=child.pid, child_start=_start_ticks(child.pid))
    last_s = time.time()

    def beat(now_s: float) -> float:
        """Touch the heartbeat and log the GPU time since the last logged beat; returns the new "last logged" time. A
        beat that cannot be written (a full disk) must not end the wrapper: the next one covers the gap."""
        try:
            heartbeat.touch()
            if on_gpu:
                budget.log_interval(task, name, budget.CUDA, last_s, now_s, pids=(child.pid,))
                return now_s
        except OSError as err:
            print(f"[ste job] beat not written ({err})", flush=True)
        return last_s

    while True:
        try:
            code = child.wait(timeout=record["beat_s"])
            break
        except subprocess.TimeoutExpired:
            last_s = beat(time.time())
    ended_s = time.time()
    beat(ended_s)
    record_end(code if code >= 0 else SIGNAL_EXIT_BASE - code, ended_s, signal.Signals(-code).name if code < 0 else None)
    return EXIT_DONE


# ================================================================================================ wait
def verdict(exit_code: int | None, effective_s: float, expected_min_s: float) -> tuple[str, int]:
    """(verdict word, the waiter's exit status) for a job that has ended. ``exit_code``: the job's own, None if none
    was recorded. See the module docstring for the rule."""
    if exit_code is None:
        return DIED, EXIT_DIED
    if effective_s < expected_min_s:
        return ENDED_EARLY, EXIT_ENDED_EARLY if exit_code == EXIT_DONE else exit_code
    return EXIT_NAMES.get(exit_code, FAILED), exit_code


def _own_pids(job: dict[str, Any]) -> tuple[int, ...]:
    """The pids a pause must have stopped to count for this job: its command's (``gpu_pause.sh`` never stops the
    wrapper). None at all if the command never started: then no pause stopped the job."""
    return () if job["child_pid"] is None else (job["child_pid"],)


def _identity(job: dict[str, Any]) -> tuple:
    return job["pid"], job["pid_start"], job["boot_id"]


def _recorded_exit_code(job: dict[str, Any], current: bool) -> int | None:
    """The exit code the wrapper wrote for this launch, or None. ``current``: the run folder's latest launch is this
    one; otherwise a relaunch has moved the file to ``exit_code.<launch>``."""
    path = Path(job["run_dir"]) / (EXIT_FILE if current else f"{EXIT_FILE}.{job['launch']}")
    try:
        return int(path.read_text())
    except (FileNotFoundError, ValueError):
        return None


def _mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return None


def _last_sign_of_life_s(run_dir: Path) -> float | None:
    """The newest modification time among the files directly in the run folder (the heartbeat, the log, a checkpoint):
    the latest moment the job is known to have been alive. None for an empty or missing folder."""
    try:
        times = [found for found in (_mtime(path) for path in run_dir.iterdir() if path.is_file()) if found is not None]
    except FileNotFoundError:
        return None
    return max(times, default=None)


def wait(name: str, poll_s: float = POLL_S) -> Outcome:
    """Block until the job ``name`` is no longer alive, then say how it ended. :class:`NoSuchJob` if it is unknown."""
    job = state.read()["jobs"].get(name)
    if job is None:
        raise NoSuchJob(name)
    watched, current = _identity(job), True
    while True:
        latest = state.read()["jobs"].get(name)
        current = latest is not None and _identity(latest) == watched
        if not current:                                          # relaunched or removed meanwhile: judge what was seen
            break
        job = latest
        if not state.job_alive(job):
            newest = state.read()["jobs"].get(name)              # the wrapper's last update may be newer than ``job``
            current = newest is not None and _identity(newest) == watched
            job = newest if current else job
            break
        time.sleep(poll_s)
    run_dir = Path(job["run_dir"])
    exit_code = _recorded_exit_code(job, current)
    if exit_code is None:
        ended_s = max(job["started"], _last_sign_of_life_s(run_dir) or job["started"]) if current else job["started"]
    else:
        ended_s = job["ended"] if job["ended"] is not None else (_mtime(run_dir / EXIT_FILE) or job["started"])
    duration_s = ended_s - job["started"]
    effective_s = pauses.effective_seconds(job["started"], ended_s, _own_pids(job))
    word, status = verdict(exit_code, effective_s, job["expected_min_s"])
    shown = "none" if exit_code is None else str(exit_code)
    line = f"{job['task']} {name} {word} exit={shown}"
    if word == ENDED_EARLY:
        line += f" ({EXIT_NAMES.get(exit_code, FAILED)})"
    line += f" duration={duration_s:.1f}s effective={effective_s:.1f}s"
    if word == ENDED_EARLY:
        line += f" expected_min={job['expected_min_s']:.1f}s"
    if word == DIED:
        line += f" (no exit code recorded; {state.job_status(job)})"
    return Outcome(line, status, word, exit_code, duration_s, effective_s)


# ================================================================================================ status
def status_lines() -> list[str]:
    """One line per job of ``state.json``, in name order; one line saying so when there is none."""
    recorded = state.read()["jobs"]
    if not recorded:
        return ["no job has been launched"]
    lines = []
    for name in sorted(recorded):
        job = recorded[name]
        word = state.job_status(job)
        if word == state.ALIVE and job["child_pid"] is not None and state.process_state(job["child_pid"]) == _STOPPED:
            word = PAUSED                                        # the owner's pause stops the command, not the wrapper
        exit_code = _recorded_exit_code(job, current=True)
        shown = "none" if exit_code is None else f"{exit_code} ({EXIT_NAMES.get(exit_code, FAILED)})"
        began = datetime.datetime.fromtimestamp(job["started"]).astimezone().isoformat(timespec="seconds")
        lines.append(f"{name}  {job['task']}  {word}  exit={shown}  pid={job['pid']} launch={job['launch']} "
                     f"started={began} gpu_h={job['gpu_h']} run_dir={job['run_dir']}")
    return lines
