"""The automatic post-run step of a training job: its 3-D Isaac Lab clips (STE L5; owner, 25 Nov 2026: "make the L5 clips
render in 3D isaac lab automatically along with the 2D top view"). Linux only, standard library only.

**On by default for the training driver's runs, by command** (lead's decision, 25 Nov 2026; never by task ID: the
clips jobs, pilots and evaluations share the run's task). ``scripts/ste_job.py launch`` turns the hook on when the
launched command runs ``scripts/ste_exploit_l012.py`` as a run of record (:func:`drives_training`: not ``--pilot``,
which writes ``pilot.json`` only; not ``--run0``, which writes no ``results.json`` and no INFO batch; not the
``verdict`` sub-command). It is the one training driver whose run folder the clip script draws (``results.json``,
``agent_final.pt`` and the INFO batch ``eval_info.npz``); ``scripts/ste_tier2_l013.py`` also writes
``results.json`` and ``agent_final.pt`` but no ``eval_info.npz``, so it is left off. ``--post-clips3d`` turns the hook
on for any other command, ``--no-post-clips3d`` turns it off. The decision is recorded as ``post_clips3d`` in
``job.json`` and replayed by ``cmd.txt``. A clips job (``clips3d_for``) never has it: the launcher refuses the two
together, and a job carrying ``clips3d_for`` only reports its end.

**When it fires.** The training job's wrapper (``ste/jobs.py`` :func:`~svg_training.ste.jobs.run_wrapper`) calls
:func:`after_end` after the command's exit code and its last GPU-hour line are written. It starts the clips only if
the command exited 0 and the run folder holds a complete ``results.json`` (``complete: true``) and ``agent_final.pt``.
A non-zero exit: one line in the run's ``job.log``, nothing written in the run folder (a failed run owes no clips).
Exit 0 without a finished run: ``skipped: <why>`` in ``HOOK_STATUS``. Clips already complete
(``videos3d/clips3d.json``) are not drawn again. While a clips job of the run is alive (its run folder
``<run>/videos3d`` or its name), nothing is done and ``HOOK_STATUS`` is left as it is ("clips job already running").

**What it starts.** ``<the training command's python> scripts/ste_l5_clips3d.py --run-dir <run>`` as its own recorded
job through :func:`~svg_training.ste.jobs.launch`: name ``clips3d_<training job>``, run folder ``<run>/videos3d`` (the
clip script's default ``--out``: its job files sit beside the clips), the run's task, settings file and beat,
``--gpu-h`` :data:`CLIPS3D_GPU_H` and ``--min-s`` :data:`CLIPS3D_MIN_S` (as the six hand launches of 25 Nov 2026; one
clips job measured 0.02-0.03 GPU-h). So its GPU-hours land in the ledger and count against the run's task cap and phase
cap, and the launcher's own refusals hold (an open owner pause, the cap). The python (the clip script needs torch) is
the interpreter the launch recorded in its command (``job.json`` ``cmd``: the first word that names a python, so
``env ... nice <python> ...`` works too); if the command names none, the fallback is this process's interpreter, which
is the one that ran ``scripts/ste_job.py launch`` (the wrapper is started with it).

**Never waits, never fails the run.** The hook makes one attempt and records the outcome in ``<run>/videos3d/
HOOK_STATUS``; it never sleeps (the waiter of the training job blocks while the wrapper lives) and never resumes a
pause. Before launching it runs ``scripts/isaac_preflight.sh --approved-headless --allow-siblings`` (the clip script runs
it again before Isaac starts): a busy GPU, an open owner pause or a refused launch (the cap) leave ``pending: <why>``
with the retry line ``scripts/ste_job.py post-clips3d --run-dir <run>`` (:func:`retry`; the same checks, by hand, once
the GPU is free or the owner has resumed). The clips job's own wrapper rewrites ``HOOK_STATUS`` when it ends (``done``,
``pending`` for exit 11 GPU busy or an interruption, ``failed`` otherwise). Any error of the hook is said in
``job.log``; the training job's exit code, its ``exit_code`` file and its results are written before the hook runs
and are never touched by it.

``HOOK_STATUS`` is plain text, first line ``<state>: <why>`` with state ``launched``, ``pending``, ``skipped``,
``done`` or ``failed``; then the time, the jobs and the retry line. ``scripts/ste_job.py status`` shows
``clips3d=<state>`` on the training job's line (:func:`hook_state`): ``running`` while the clips job lives; the
marker's word; ``missing`` for an exit-0 run with the hook on whose clips are not complete and whose clips job is not
alive and left no word (the wrapper was killed or the machine rebooted before the hook ran, or the clips job died).
Nothing is retried on its own: the retry line does it.
"""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import os
import re
import signal

from . import atomic, jobs, state
from .run_contract import EXIT_DONE, EXIT_INTERRUPTED, EXIT_REFUSED

CLIPS3D_DIR = "videos3d"                  # scripts/ste_l5_clips3d.py DEFAULT_OUT
CLIPS_JSON = "clips3d.json"              # scripts/ste_l5_clips3d.py CLIPS_JSON
HOOK_STATUS = "HOOK_STATUS"
PREFLIGHT_LOG = "hook_preflight.txt"
RUN_FILES = ("results.json", "agent_final.pt")
CLIPS3D_GPU_H = 0.1                      # GPU-hours asked per clips job (the hand launches' ask, 25 Nov 2026)
CLIPS3D_MIN_S = 30.0                     # its expected minimum duration, seconds (the hand launches' --min-s)
CLIPS_SCRIPT = jobs.WRAPPER_SCRIPT.parent / "ste_l5_clips3d.py"
PREFLIGHT_SCRIPT = jobs.WRAPPER_SCRIPT.parent / "isaac_preflight.sh"
PREFLIGHT_ARGS = ("--approved-headless", "--allow-siblings")
PREFLIGHT_TIMEOUT_S = 120.0
EXIT_GPU_BUSY = 11                       # the preflight's and the clip script's "GPU busy"
RETRYABLE = {EXIT_GPU_BUSY: "the GPU was busy", EXIT_INTERRUPTED: "interrupted",
             jobs.SIGNAL_EXIT_BASE + 2: "interrupted (SIGINT)", jobs.SIGNAL_EXIT_BASE + 15: "stopped (SIGTERM)"}
LAUNCHED, PENDING, SKIPPED, DONE, FAILED = "launched", "pending", "skipped", "done", "failed"
RUNNING, MISSING = "running", "missing"            # status only, never written to HOOK_STATUS
TRAINING_DRIVER = "ste_exploit_l012.py"           # the driver whose runs the clip script draws
NOT_A_RUN = ("--pilot", "--run0")                  # its modes that leave no run of record
_PYTHON = re.compile(r"python[0-9.]*")
TAG = "[ste job] post-run clips3d"

Say = Callable[[str], None]


def clips_name(training_name: str) -> str:
    """The clips job's name: ``clips3d_<training job>`` (still letters, digits, ``.``, ``_``, ``-``)."""
    return f"clips3d_{training_name}"


def drives_training(cmd: list[str]) -> bool:
    """True when ``cmd`` runs the training driver (``scripts/ste_exploit_l012.py``) as a run of record: the default of
    ``launch``'s hook. Not its ``--pilot`` or ``--run0`` modes, not its ``verdict`` sub-command."""
    words = [str(word) for word in cmd]
    at = next((k for k, word in enumerate(words) if Path(word).name == TRAINING_DRIVER), None)
    if at is None:
        return False
    rest = words[at + 1:]
    return not (rest[:1] == ["verdict"] or any(word in NOT_A_RUN for word in rest))


def clips_python(record: dict[str, Any]) -> str:
    """The interpreter recorded in the launch's command (the first word naming a python), else this process's: the one
    that ran ``scripts/ste_job.py launch``, since the wrapper is started with it."""
    return next((str(word) for word in record.get("cmd", []) if _PYTHON.fullmatch(Path(str(word)).name)),
                sys.executable)


def clips_command(record: dict[str, Any], run: Path) -> list[str]:
    """``<python> scripts/ste_l5_clips3d.py --run-dir <run>`` (:func:`clips_python`)."""
    return [clips_python(record), str(CLIPS_SCRIPT), "--run-dir", str(run)]


def run_problem(run: Path) -> str | None:
    """Why the run folder is not a finished run (None if it is): ``results.json`` with ``complete: true`` and
    ``agent_final.pt``."""
    try:
        results = json.loads((run / "results.json").read_text())
    except (OSError, ValueError):
        return f"{run / 'results.json'} is missing or unreadable"
    if not isinstance(results, dict) or results.get("complete") is not True:
        return f"{run / 'results.json'} is not complete"
    if not (run / "agent_final.pt").is_file():
        return f"{run / 'agent_final.pt'} is missing"
    return None


def clips_complete(out: Path) -> bool:
    try:
        return json.loads((out / CLIPS_JSON).read_text()).get("complete") is True
    except (OSError, ValueError, AttributeError):
        return False


def _exit_code(folder: Path) -> int | None:
    """The exit code a job's wrapper recorded in ``folder`` (``exit_code``), or None."""
    try:
        return int((folder / jobs.EXIT_FILE).read_text())
    except (OSError, ValueError):
        return None


def preflight(log: Path) -> int:
    """``scripts/isaac_preflight.sh --approved-headless --allow-siblings``; its output to ``log``; its exit code (124 if
    it did not answer within PREFLIGHT_TIMEOUT_S)."""
    proc = subprocess.Popen(["bash", str(PREFLIGHT_SCRIPT), *PREFLIGHT_ARGS], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        text, _ = proc.communicate(timeout=PREFLIGHT_TIMEOUT_S)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)       # the script and anything it started (a stuck nvidia-smi)
        except ProcessLookupError:
            pass
        proc.communicate()
        text, code = f"no answer within {PREFLIGHT_TIMEOUT_S:.0f} s\n", 124
    atomic.write_text(log, text)
    return code


def retry_line(run: Path, record: dict[str, Any]) -> str:
    """The shell line that runs the hook again by hand, with the launch's recorded environment (as ``cmd.txt``)."""
    argv = [sys.executable, str(jobs.WRAPPER_SCRIPT), "post-clips3d", "--run-dir", str(run)]
    return jobs.relaunch_line(record.get("cwd", str(jobs.WRAPPER_SCRIPT.parents[1])), argv, record.get("env", {}))


def write_status(run: Path, word: str, why: str, record: dict[str, Any], clips: str) -> None:
    """``<run>/videos3d/HOOK_STATUS``: ``<word>: <why>``, the time, the clips job, the retry line."""
    out = run / CLIPS3D_DIR
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [f"{word}: {why}", f"time: {now}", f"run: {run}", f"clips job: {clips} (run folder {out})",
             f"retry: {retry_line(run, record)}"]
    atomic.write_text(out / HOOK_STATUS, "\n".join(lines) + "\n")


def after_end(run_dir: Path, record: dict[str, Any], exit_code: int, say: Say) -> None:
    """Called by the wrapper once the command's end is recorded. A clips job (``clips3d_for`` in its ``job.json``)
    writes its outcome to its run's ``HOOK_STATUS``; a training job launched with ``--post-clips3d`` fires the hook."""
    if record.get("clips3d_for"):
        clips_ended(Path(record["clips3d_for"]), record, exit_code, say)
    elif record.get("post_clips3d"):
        fire(Path(run_dir), record, exit_code, say)


def fire(run: Path, record: dict[str, Any], exit_code: int | None, say: Say) -> str:
    """One attempt to start the clips of the finished run ``run`` whose training job is ``record`` (its ``job.json``)
    and ended with ``exit_code``. Returns the state word (``running`` if a clips job of the run is alive: nothing
    done); never waits."""
    out = run / CLIPS3D_DIR
    name = clips_name(record["name"])
    alive = live_clips_job(run, name)
    if alive is not None:
        say(f"{TAG}: clips job already running ({alive}); nothing done")
        return RUNNING
    if exit_code != 0:
        say(f"{TAG}: not started (the training job exited {exit_code}, not 0)")
        return SKIPPED

    def mark(word: str, why: str) -> str:
        write_status(run, word, why, record, name)
        say(f"{TAG}: {word}: {why} ({out / HOOK_STATUS})")
        return word

    problem = run_problem(run)
    if problem is not None:
        return mark(SKIPPED, f"the training job exited 0 but the run is not finished: {problem}")

    if clips_complete(out):
        drawn = _exit_code(out)
        if drawn not in (None, 0):          # a clips job that finished with exit 1 or 3: its marker stays a failure
            return mark(FAILED, f"{out / CLIPS_JSON} is complete but its clips job exited {drawn}; the clip script "
                                f"refuses a finished folder: new clips need a new --out")
        return mark(SKIPPED, f"the 3-D clips are complete already ({out / CLIPS_JSON})")
    owners = jobs.owner_pause_lines()
    if owners:
        return mark(PENDING, f"{owners[0]} is still open: nothing was launched (only the owner ends it); 3-D clips "
                             f"pending")
    out.mkdir(parents=True, exist_ok=True)
    code = preflight(out / PREFLIGHT_LOG)
    if code != 0:
        return mark(PENDING, f"the GPU is not free (scripts/isaac_preflight.sh {' '.join(PREFLIGHT_ARGS)}: preflight "
                             f"exit {code}, {out / PREFLIGHT_LOG}): nothing was launched; 3-D clips pending")
    try:
        job = jobs.launch(record["task"], name, out, clips_command(record, run), CLIPS3D_MIN_S, CLIPS3D_GPU_H,
                          settings=record["settings"], beat_s=record["beat_s"], cwd=record["cwd"], clips3d_for=run)
    except jobs.LaunchRefused as err:
        return mark(PENDING, f"the launch was refused: {err}; 3-D clips pending")
    write_status(run, LAUNCHED, f"job {name} (task {record['task']}, --gpu-h {CLIPS3D_GPU_H}, pid {job['pid']}); "
                                f"scripts/ste_job.py wait {name}", record, name)
    say(f"{TAG}: launched {name} (task {record['task']}, --gpu-h {CLIPS3D_GPU_H}, pid {job['pid']}, run folder {out})")
    return LAUNCHED


def live_clips_job(run: Path, name: str | None = None) -> str | None:
    """The name of a live job whose run folder is ``<run>/videos3d`` or whose name is ``name``, else None."""
    out = Path(run) / CLIPS3D_DIR
    for other, job in state.read()["jobs"].items():
        if (Path(job["run_dir"]) == out or other == name) and state.job_alive(job):
            return other
    return None


def clips_ended(run: Path, record: dict[str, Any], exit_code: int, say: Say) -> str:
    """The clips job of ``run`` (its ``job.json``: ``record``) ended with ``exit_code``: write ``HOOK_STATUS``."""
    out, name = Path(record["run_dir"]), record["name"]
    if exit_code == 0 and clips_complete(out):
        word, why = DONE, f"job {name} exit 0; the 3-D clips and {CLIPS_JSON} are in {out}"
    elif exit_code in RETRYABLE:
        word, why = PENDING, f"job {name} exit {exit_code} ({RETRYABLE[exit_code]}); 3-D clips pending"
    else:
        word, why = FAILED, (f"job {name} exit {exit_code}"
                             f"{'' if clips_complete(out) else f', {CLIPS_JSON} not complete'}; see {out / 'job.log'}")
    write_status(run, word, why, record, name)
    say(f"{TAG}: {word}: {why}")
    return word


def retry(run: Path, say: Say = print) -> int:
    """``scripts/ste_job.py post-clips3d --run-dir <run>``: the hook again, by hand, for a finished training run (its
    ``job.json`` and ``exit_code``). 0 if the clips job was launched, 2 otherwise (the reason is printed)."""
    run = Path(run).resolve()
    try:
        record = json.loads((run / jobs.JOB_FILE).read_text())
    except (OSError, ValueError):
        say(f"refused: {run / jobs.JOB_FILE} is missing or unreadable (not a launched run folder)")
        return EXIT_REFUSED
    live = state.read()["jobs"].get(record.get("name"))
    if live is not None and Path(live["run_dir"]) == run and state.job_alive(live):
        say(f"refused: job {record['name']} is still {state.job_status(live)}")
        return EXIT_REFUSED
    word = fire(run, record, _exit_code(run), say)
    return EXIT_DONE if word == LAUNCHED else EXIT_REFUSED


def hook_state(run: Path, recorded: dict[str, dict[str, Any]]) -> str | None:
    """The clips state of a training run for ``status`` (None: nothing to show). ``running`` while a clips job of the
    run lives; else the word of ``HOOK_STATUS`` (``pending``, ``skipped``, ``done``, ``failed``); ``missing`` when the
    marker says ``launched`` but the clips job is gone without a word, or when there is no marker for an exit-0 run
    with the hook on (``job.json`` ``post_clips3d``) whose ``clips3d.json`` is not complete: the wrapper was killed
    or the machine rebooted before the hook ran."""
    run = Path(run)
    out = run / CLIPS3D_DIR
    if any(Path(job["run_dir"]) == out and state.job_alive(job) for job in recorded.values()):
        return RUNNING
    try:
        word: str | None = (out / HOOK_STATUS).read_text().splitlines()[0].split(":", 1)[0]
    except (OSError, IndexError):
        word = None
    if word == LAUNCHED:
        return MISSING
    if word is not None:
        return word
    try:
        hooked = json.loads((run / jobs.JOB_FILE).read_text()).get("post_clips3d") is True
    except (OSError, ValueError, AttributeError):
        hooked = False
    if hooked and _exit_code(run) == 0 and not clips_complete(out):
        return MISSING
    return None
