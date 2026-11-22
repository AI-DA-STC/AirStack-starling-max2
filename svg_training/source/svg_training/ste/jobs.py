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
unpaused; a pause the lead tagged ``GPU_PAUSE_BY=lead`` to run a solo job beside its paused siblings does not block,
``ste/pauses.py``), while a job of the same name, or any job in the same run folder, is alive, and when ``ste/budget.py`` says
the hours asked for would pass the task's cap or the phase cap, or the task's phase is closed. The hours asked for
are the job's total over all its launches in its run folder, so the hours it has already logged there are not asked for a
second time at a relaunch; a new run folder under an old job name is a new run and gets no such credit.

Files in the run folder: ``job.json`` (the launch record: the ``state.json`` fields of ``ste/state.py`` plus the job
name, the beat, the shared folder and a few environment variables), ``cmd.txt`` (the launch command line, to run again
by hand: ``bash <run folder>/cmd.txt``; see :func:`relaunch_line`),
``job.log``, ``exit_code`` (``exit_code.<n>`` once launch ``n`` has been followed by a relaunch), ``heartbeat``
(touched by the wrapper every beat: its modification time is when the job was last seen alive), ``launches.jsonl``
(one line per launch and per end). A GPU job (``gpu_h`` above 0) also gets one line per beat in the GPU-hour ledger.

**Wait.** Blocks until the job is no longer alive, by the test of ``ste/state.py`` (pid, start time, boot id, of the
wrapper or of the command); it never looks at process names or command lines, so a waiter whose own command line
names the job cannot match itself. Then one line::

    <task> <job> <VERDICT> exit=<code> duration=<s>s effective=<s>s

and its own exit status:

* the job's exit code, whatever it is (verdict DONE, CAP, NONFINITE, CONTROL_FAILED, INTERRUPTED, REFUSED as
  ``ste/run_contract.py`` names them, FAILED for any other code);
* **ENDED_EARLY** when the effective duration (wall clock less the owner's pauses that stopped the job's command) is
  under the expected minimum given at launch. For a trainer that keeps the run contract (``ste/run_contract.py``)
  the duration judged is the larger of this launch's and the WHOLE run's: the run folder's effective seconds the
  trainer wrote in ``progress.json`` with its checkpoint, if it wrote it during this launch (L07-I4). So a run resumed
  after a power cut (the same line, or ``bash cmd.txt``) is judged on its whole run, the line then shows
  ``run_effective=<s>s``; a relaunch that saves nothing is judged on its own time. Status :data:`EXIT_ENDED_EARLY`
  if the job's code was 0 (a 0 that came too fast must not pass), else the job's own code;
* **DIED** when the job is gone and no exit code was recorded (killed with its wrapper, or lost with a previous
  boot): status :data:`EXIT_DIED`. The duration then runs to the job's last sign of life: the newest file of its
  run folder (the heartbeat, the log, a checkpoint).

A command the wrapper cannot start (a misspelt program) is recorded with exit code :data:`EXIT_NOT_STARTED`. If the
waiter itself fails (``state.json`` unreadable) its status is :data:`EXIT_TOOL_ERROR`, never one a job could return.

**Status.** One line per job of ``state.json``: alive, alive (paused), alive (wrapper gone), dead, or dead (previous
boot), with the exit code if one was recorded.

**Faults.** A write the wrapper had to retry (a full disk, any error; :func:`run_wrapper`) is counted in ``job.json``
(``faults``, ``last_fault``); the waiter's line then ends with ``faults=<n> (...)`` and the status line shows
``faults=<n>``. The verdict and the waiter's status are not changed by it. Standard library only.
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
from .config import SETTINGS_FILE, phase_of
from .run_contract import EXIT_DONE, EXIT_NAMES, EXIT_REFUSED, PROGRESS_NAME

EXIT_ENDED_EARLY = 20        # waiter: the job exited 0 but in less than its expected minimum
EXIT_DIED = 21               # waiter: the job is gone and recorded no exit code
EXIT_NO_SUCH_JOB = 22        # waiter: state.json has no job of that name
EXIT_TOOL_ERROR = 23         # wait or status failed itself (an unreadable state.json): never a job's code
EXIT_NOT_STARTED = 127       # recorded for a command the wrapper could not start, as a shell reports "not found"
SIGNAL_EXIT_BASE = 128       # a command killed by signal n is recorded as 128 + n, as a shell reports it
POLL_S = 1.0                 # how often the waiter looks
BEAT_S = 60.0                # how often the wrapper touches the heartbeat and logs GPU time
RECORD_ATTEMPTS = 10         # how often the wrapper tries to record an ended command's exit code, one beat apart

DONE, FAILED, ENDED_EARLY, DIED = EXIT_NAMES[EXIT_DONE], "FAILED", "ENDED_EARLY", "DIED"
PAUSED = "alive (paused)"

WRAPPER_SCRIPT = shared.PACKAGE_DIR.parents[2] / "scripts" / "ste_job.py"
WRAPPER_COMMAND = "_run"
JOB_FILE, CMD_FILE, LOG_FILE, EXIT_FILE = "job.json", "cmd.txt", "job.log", "exit_code"
HEARTBEAT_FILE, LAUNCHES_FILE = "heartbeat", "launches.jsonl"
RECORDED_ENV = ("PYTHONPATH", "CUDA_VISIBLE_DEVICES", "PYTORCH_CUDA_ALLOC_CONF", shared.SHARED_ENV,
                shared.LEGACY_LOGS_ENV)    # set again, or unset, by cmd.txt exactly as at the launch
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
    run_effective_s: float | None = None     # the whole run's effective seconds (trainer's progress.json), if judged


def _run_effective_s(job: dict[str, Any]) -> float | None:
    """The run folder's effective seconds as the trainer recorded them with its latest checkpoint (``progress.json``,
    ``ste/run_contract.py``), only if that was saved during this launch; None otherwise (no trainer contract, nothing
    saved since the launch, an unreadable file)."""
    try:
        progress = json.loads((Path(job["run_dir"]) / PROGRESS_NAME).read_text())
        effective_s, saved_s = progress["effective_s"], progress["saved"]
        if type(effective_s) in (int, float) and type(saved_s) in (int, float) and math.isfinite(effective_s) \
                and saved_s >= job["started"]:
            return float(effective_s)
    except Exception:                                            # a missing or torn file: judge the launch alone
        pass
    return None


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


def owner_pause_lines() -> list[str]:
    """One line per open owner pause (``ste/pauses.py``: any open pause not tagged ``lead``), oldest first."""
    lines = []
    for paused in pauses.owner_pauses():
        made = datetime.datetime.fromtimestamp(paused["time"]).astimezone().isoformat(timespec="seconds")
        lines.append(f"the owner's pause of {made} (by {paused.get('by', 'unknown')}, pids {paused.get('pids')})")
    return lines


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
    run_dir = Path(run_dir).resolve()
    _check_shared_folder(run_dir)                                # before anything reads or makes the shared folder
    owners = owner_pause_lines()                                 # the session's own pauses (by "lead") do not block
    if owners:
        more = f" and {len(owners) - 1} more" if len(owners) > 1 else ""
        raise LaunchRefused(f"{owners[0]}{more} is still open: nothing was launched. Only the owner ends it, with "
                            f"scripts/gpu_pause.sh resume; launch again after that")
    try:
        budget.check_launch(task, gpu_h, settings, job=name, run_dir=str(run_dir))
    except budget.BudgetError as err:
        raise LaunchRefused(str(err)) from err
    settings = Path(settings).resolve()
    phase = phase_of(task)                                       # the launched task's phase, not the phase in work
    cwd = Path(cwd if cwd is not None else os.getcwd()).resolve()
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
                                                              settings=str(settings), env=environment,
                                                              shared_dir=str(_shared_folder())), indent=1) + "\n")
        again = [sys.executable, str(WRAPPER_SCRIPT), "launch", "--task", task, "--name", name, "--run-dir", str(run_dir),
                 "--min-s", repr(float(expected_min_s)), "--gpu-h", repr(float(gpu_h)), "--settings", str(settings),
                 "--beat-s", repr(float(beat_s)), "--", *cmd]
        atomic.write_text(run_dir / CMD_FILE, f"# launch {number} of job {name} (task {task}); run it with bash: it "
                                              f"sets or unsets {', '.join(RECORDED_ENV)} as at this launch\n"
                                              f"{relaunch_line(cwd, again, environment)}\n")
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


def relaunch_line(cwd: Path | str, argv: list[str], environment: dict[str, str]) -> str:
    """The shell line of ``cmd.txt``: ``cd <cwd> && env -u <absent>... <KEY=VALUE>... <argv>``. ``environment``: the
    values of :data:`RECORDED_ENV` at the launch, absent keys left out. A key set at the launch is set again to the
    same text (an empty ``CUDA_VISIBLE_DEVICES`` stays empty: unset would show the GPU); a key absent at the launch is
    unset, so a new shell's ``PYTHONPATH`` (ROS) or ``SVG_SHARED_DIR`` cannot leak in. Every word is quoted."""
    unset = [word for key in RECORDED_ENV if key not in environment for word in ("-u", key)]
    assigned = [f"{key}={environment[key]}" for key in RECORDED_ENV if key in environment]
    return f"cd {shlex.quote(str(cwd))} && {shlex.join(['env', *unset, *assigned, *argv])}"


def _shared_folder() -> Path:
    """The shared folder this process uses, resolved, without making it."""
    return shared.shared_dir(create=False).resolve()


def _check_shared_folder(run_dir: Path) -> None:
    """Refuse a relaunch whose shared folder differs from the one the run folder recorded at its last launch: its
    state, GPU-hours and pauses would be counted where the waiter, the status and the budget check do not look. A
    ``job.json`` written before L07-I2 records none and is not checked."""
    previous = _read_json(run_dir / JOB_FILE)
    recorded = None if previous is None else previous.get("shared_dir")
    if recorded is not None and Path(recorded) != _shared_folder():
        raise LaunchRefused(f"run folder {run_dir} was launched with the shared folder {recorded} (state.json, GPU-hour "
                            f"ledger, pause log); this launch would use {_shared_folder()}: nothing was launched. "
                            f"Relaunch with bash {run_dir / CMD_FILE}, or set {shared.SHARED_ENV}={recorded}")


# ================================================================================================ the wrapper
def _say(text: str) -> None:
    """One line to the wrapper's output (the run's ``job.log``); a line that cannot be written (a full disk) is lost,
    never fatal."""
    try:
        print(text, flush=True)
    except OSError:
        pass


def _update_own_record(name: str, pid_start: int, **changes: Any) -> Exception | None:
    """Set fields of this wrapper's job in ``state.json``; a record that is no longer this wrapper's is left alone.
    Returns the error if the file could not be written (an unreadable state, a full disk, any error), None if it
    was."""
    def change(data: dict[str, Any]) -> None:
        job = data["jobs"].get(name)
        if job is not None and (job["pid"], job["pid_start"], job["boot_id"]) == (os.getpid(), pid_start, state.boot_id()):
            job.update(changes)

    try:
        state.update(change)
    except Exception as err:                                     # the exit_code file is the record that counts
        return err
    return None


def run_wrapper(run_dir: Path | str) -> int:
    """The wrapper process (``scripts/ste_job.py _run <run folder>``): run the launch's command, pass SIGINT and
    SIGTERM on to it, beat while it runs, record its exit code when it ends.

    **No bookkeeping error ends the wrapper while its command runs** (L07-I3). A write that fails (the heartbeat, a
    ledger line, ``state.json``, any error, a full disk included) is said in ``job.log``, counted in ``job.json``
    (``faults``, ``last_fault``: the waiter and the status show them) and tried again at the next beat; a ledger line
    that failed is covered by the next one, which starts where the last written one ended. The clock the wrapper uses
    never goes back: after a backward step of the wall clock it stays at the latest reading until the wall clock
    catches up, so no interval is negative or counted twice (the GPU time of the step itself is not logged). When the
    command ends, the ``exit_code`` file and the last ledger line are retried one beat apart until both are written,
    at most :data:`RECORD_ATTEMPTS` times; ``state.json`` and the ``launches.jsonl`` row are tried alongside but do
    not keep the wrapper waiting."""
    run_dir = Path(run_dir)
    with state.locked():                                         # held by the launcher until the launch is recorded
        pass
    record = _read_json(run_dir / JOB_FILE)
    own_start = _start_ticks(os.getpid())
    if record is None or (record["pid"], record["pid_start"], record["boot_id"]) != (os.getpid(), own_start, state.boot_id()):
        print(f"[ste job] {run_dir / JOB_FILE} does not record this wrapper (pid {os.getpid()}): nothing is run",
              flush=True)
        return EXIT_REFUSED
    name, task, on_gpu, beat_s = record["name"], record["task"], record["gpu_h"] > 0, record["beat_s"]
    child: subprocess.Popen | None = None
    early: list[int] = []
    faults: dict[str, Any] = {"faults": 0, "last_fault": None}
    unsaved: dict[str, Any] = {}                                 # state.json fields not yet written
    flag_unsaved = [False]                                       # job.json's fault count not yet written
    latest = [time.time()]
    logged = [latest[0]]                                         # the end of the last ledger line written

    def log_gpu(now_s: float) -> None:
        """One ledger line from the end of the last one written to ``now_s`` (a GPU job; nothing if no time passed)."""
        if on_gpu and child is not None and now_s > logged[0]:
            try:
                budget.log_interval(task, name, budget.CUDA, logged[0], now_s, pids=(child.pid,),
                                    run_dir=record["run_dir"])
                logged[0] = now_s
            except Exception as err:
                fault("GPU-hour line not written", err)

    def clock() -> float:
        """Unix seconds that never go back (the latest wall-clock reading so far)."""
        latest[0] = max(latest[0], time.time())
        return latest[0]

    def fault(what: str, err: BaseException) -> None:
        faults["faults"] += 1
        faults["last_fault"] = f"{what}: {type(err).__name__}: {err}"
        flag_unsaved[0] = True
        _say(f"[ste job] FAULT {faults['faults']}: {faults['last_fault']} (tried again at the next beat)")

    def save_records() -> bool:
        """Write what is not yet written (state.json fields, job.json's fault count); True when nothing is left."""
        if unsaved:
            err = _update_own_record(name, own_start, **unsaved)
            if err is None:
                unsaved.clear()
            else:
                fault("state.json not updated", err)
        if flag_unsaved[0]:
            try:
                atomic.write_text(run_dir / JOB_FILE, json.dumps(dict(record, **faults), indent=1) + "\n")
                flag_unsaved[0] = False
            except Exception as err:
                faults["last_fault"] = f"job.json not updated: {type(err).__name__}: {err}"
                _say(f"[ste job] {faults['last_fault']}")
        return not unsaved and not flag_unsaved[0]

    def pass_on(number: int, frame: Any) -> None:
        if child is None:
            early.append(number)
        else:
            child.send_signal(number)                            # does nothing once the command has ended

    def record_end(exit_code: int, ended_s: float, signal_name: str | None) -> None:
        """Record the end: the exit_code file and the last ledger line are retried, one beat apart, until both are
        written (at most RECORD_ATTEMPTS tries); state.json and the launches.jsonl row are tried alongside but do
        not hold the wrapper (the exit_code file is the record that counts)."""
        unsaved.update(exit_code=exit_code, ended=ended_s)
        written = [False, False]                                 # the exit_code file, the launches.jsonl end row
        for attempt in range(RECORD_ATTEMPTS):
            if attempt:
                time.sleep(beat_s)
            log_gpu(ended_s)
            if not written[0]:
                try:
                    atomic.write_text(run_dir / EXIT_FILE, f"{exit_code}\n")
                    written[0] = True
                except Exception as err:
                    fault("exit_code not written", err)
            if not written[1]:
                try:
                    _append(run_dir / LAUNCHES_FILE, {"event": "end", "launch": record["launch"], "time": ended_s,
                                                      "exit_code": exit_code, "signal": signal_name})
                    written[1] = True
                except Exception as err:
                    fault("launches.jsonl end row not written", err)
            save_records()
            unlogged = on_gpu and child is not None and logged[0] < ended_s
            if written[0] and not unlogged:
                return
        lost = f"; GPU time from {logged[0]} to {ended_s} not logged" if unlogged else ""
        _say(f"[ste job] FAULT: the end of the command (exit code {exit_code}) could not be fully recorded after "
             f"{RECORD_ATTEMPTS} attempts{lost}")

    for number in _FORWARDED:
        signal.signal(number, pass_on)
    heartbeat = run_dir / HEARTBEAT_FILE
    try:
        heartbeat.touch()
    except Exception as err:
        fault("heartbeat not touched", err)
    try:
        child = subprocess.Popen(record["cmd"], cwd=record["cwd"], stdin=subprocess.DEVNULL)
    except OSError as err:
        _say(f"[ste job] the command could not be started ({err}): {record['cmd']}")
        record_end(EXIT_NOT_STARTED, clock(), None)
        return EXIT_DONE
    for number in early:
        child.send_signal(number)
    try:
        unsaved.update(child_pid=child.pid, child_start=_start_ticks(child.pid))
    except Exception as err:                                     # the wrapper's own pid still keeps the job alive
        fault("the command's start time not read", err)
    save_records()
    logged[0] = clock()

    def beat(now_s: float) -> None:
        """Touch the heartbeat, log the GPU time since the last logged line, write what is not yet written. Never
        raises: a failure is a fault, and the next beat covers the gap."""
        try:
            heartbeat.touch()
        except Exception as err:
            fault("heartbeat not touched", err)
        log_gpu(now_s)
        save_records()

    while True:
        try:
            code = child.wait(timeout=beat_s)
            break
        except subprocess.TimeoutExpired:
            beat(clock())
    ended_s = clock()
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


def _faults(job: dict[str, Any]) -> tuple[int, str | None]:
    """How many bookkeeping writes the wrapper of this launch had to retry, and the last one (``job.json``)."""
    try:
        record = _read_json(Path(job["run_dir"]) / JOB_FILE)
        if not isinstance(record, dict) or record.get("launch") != job["launch"]:
            return 0, None
        count = record.get("faults", 0)
        return (count, record.get("last_fault")) if type(count) is int and count > 0 else (0, None)
    except Exception:                                            # a note only: it never changes the waiter's status
        return 0, None


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
    run_s = _run_effective_s(job) if current else None
    judged_s = effective_s if run_s is None else max(effective_s, run_s)
    word, status = verdict(exit_code, judged_s, job["expected_min_s"])
    shown = "none" if exit_code is None else str(exit_code)
    line = f"{job['task']} {name} {word} exit={shown}"
    if word == ENDED_EARLY:
        line += f" ({EXIT_NAMES.get(exit_code, FAILED)})"
    line += f" duration={duration_s:.1f}s effective={effective_s:.1f}s"
    if run_s is not None and job["launch"] > 1:
        line += f" run_effective={run_s:.1f}s"
    if word == ENDED_EARLY:
        line += f" expected_min={job['expected_min_s']:.1f}s"
    if word == DIED:
        line += f" (no exit code recorded; {state.job_status(job)})"
    count, last = _faults(job)
    if count:
        line += f" faults={count} (bookkeeping writes retried; last: {last}; see {job['log']})"
    return Outcome(line, status, word, exit_code, duration_s, effective_s, run_s)


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
        count, _ = _faults(job)
        noted = f"  faults={count}" if count else ""
        lines.append(f"{name}  {job['task']}  {word}  exit={shown}{noted}  pid={job['pid']} launch={job['launch']} "
                     f"started={began} gpu_h={job['gpu_h']} run_dir={job['run_dir']}")
    return lines
