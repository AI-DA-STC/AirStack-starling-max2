"""The trainer contract of the STE learning track (task L0.7): what every GPU job must do so that it can be launched
detached, paused by the owner, stopped at its cap, and resumed after a reboot. Linux only; standard library only (a
trainer hands in its own saver, so this module never imports PyTorch).

The contract, proved on ``scripts/ste_dummy_job.py`` by ``tests/test_ste_run_contract.py``:

1. **The same command resumes.** Run again on its run folder, the job loads the latest checkpoint and carries on.
2. **SIGINT and SIGTERM ask for a stop.** The job checkpoints at its next step boundary and exits with
   :data:`EXIT_INTERRUPTED`. (SIGKILL and a power cut cannot be caught: the job then resumes from its last checkpoint.)
3. **The cap is counted in effective time**: wall clock less the owner's pauses that stopped THIS process (its pid in
   the pause line, ``ste/pauses.py``), carried through the checkpoint, so it is one cap for the run folder however
   often the job is relaunched. A pause that stopped other jobs, or none, takes nothing off: this job ran on. At the
   cap the job checkpoints and exits with :data:`EXIT_CAP`. Each save also writes ``progress.json`` (JSON, whatever
   the checkpoint's own format): the step, the run folder's effective seconds and the save time. The waiter
   (``ste/jobs.py``) judges an early end on it, so a resumed run is judged on its whole run, not on its last launch.
4. **A non-finite value (NaN, infinity) never overwrites the last good checkpoint.** The job exits with
   :data:`EXIT_NONFINITE`; nothing retries it silently.
5. **One job per run folder.** A second copy started on the same folder is refused (:data:`EXIT_REFUSED`).

Exit codes. 0, 2, 3 and 4 are the repository's existing ones (``scripts/nus_selfplay_train.py``: ``EXIT_REFUSED``,
``EXIT_ABORTED`` at its cap, ``EXIT_STOPPED`` on SIGINT; CODING_PRACTICES section 8: "2 refused, 3 cap, 4 operator
stop"). ``scripts/train_standin.py`` uses 3 for a non-finite abort as well, so there 3 means two things; this track
needs the two told apart, and gives a non-finite value its own code, 5.

How a trainer uses :class:`RunGuard` (the pattern of ``scripts/ste_dummy_job.py``)::

    with RunGuard(run_dir, cap_s=cap_h * HOUR_S, dump=torch.save, load=torch.load) as guard:
        resumed = guard.load_latest()                      # None on a fresh run folder
        ...
        while step < steps:
            reason = guard.stop_reason()                   # "interrupted", "cap" or None
            if reason:
                guard.save(step, state)
                return EXIT_FOR_STOP[reason]
            ... one update ...
            guard.check_finite(loss=float(loss))           # raises NonFiniteError: return EXIT_NONFINITE
            if step % every == 0:
                guard.save(step, state)
        guard.save(step, state)
        return EXIT_DONE
"""
from __future__ import annotations

import fcntl
import json
import math
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Callable, NamedTuple

from . import atomic, pauses

EXIT_DONE = 0
EXIT_REFUSED = 2          # refused to start: bad arguments, the run folder is in use, the budget would be exceeded
EXIT_CAP = 3              # stopped at its cap, with a checkpoint
EXIT_INTERRUPTED = 4      # SIGINT or SIGTERM: stopped on request, with a checkpoint
EXIT_NONFINITE = 5        # a NaN or an infinity: stopped, the last good checkpoint kept
EXIT_NAMES = {EXIT_DONE: "DONE", EXIT_REFUSED: "REFUSED", EXIT_CAP: "CAP", EXIT_INTERRUPTED: "INTERRUPTED",
              EXIT_NONFINITE: "NONFINITE"}

STOP_INTERRUPTED = "interrupted"
STOP_CAP = "cap"
EXIT_FOR_STOP = {STOP_INTERRUPTED: EXIT_INTERRUPTED, STOP_CAP: EXIT_CAP}

CHECKPOINT_NAME = "checkpoint.latest"
PROGRESS_NAME = "progress.json"   # {"step", "effective_s", "saved"} of the latest checkpoint, JSON for the waiter
LOCK_NAME = "run.lock"
_STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM)


class NonFiniteError(ValueError):
    """A NaN or an infinity was found; the last good checkpoint is kept."""


class RunBusyError(RuntimeError):
    """Another process is already running in this run folder."""


class Checkpoint(NamedTuple):
    """What :meth:`RunGuard.load_latest` returns: the step the state was saved at, the trainer's own state, and the
    effective seconds (wall clock less pauses) the run folder had used when it was saved."""
    step: int
    state: Any
    effective_s: float


def _json_dump(obj: Any, path: Path | str) -> None:
    Path(path).write_text(json.dumps(obj, allow_nan=False))


def _json_load(path: Path | str) -> Any:
    return json.loads(Path(path).read_text())


def _first_non_finite(value: Any, where: str) -> str | None:
    """``"<where>: <value>"`` for the first NaN or infinity among the numbers of ``value`` (numbers, and lists, tuples
    and dicts of them, nested); None if there is none. Other objects (texts, yes/no, tensors) are not looked into."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return None if math.isfinite(value) else f"{where}: {value!r}"
    if isinstance(value, dict):
        parts = ((f"{where}.{key}", item) for key, item in value.items())
    elif isinstance(value, (list, tuple)):
        parts = ((f"{where}[{index}]", item) for index, item in enumerate(value))
    else:
        return None
    for name, item in parts:
        found = _first_non_finite(item, name)
        if found is not None:
            return found
    return None


class RunGuard:
    """One job's hold on its run folder: the lock, the stop signals, the cap clock and the checkpoint.

    ``run_dir``: the job's run folder (made if missing). ``cap_s``: the cap in effective seconds, above 0
    (``math.inf`` = no cap). ``dump(obj, path)`` and ``load(path)``: how a checkpoint is written and read; the default
    is JSON, a PyTorch trainer passes ``torch.save`` and ``torch.load``. ``clock``: unix seconds (tests).

    Use it as a context manager from the main thread (signal handlers can only be set there). Entering takes the
    folder's lock (:class:`RunBusyError` if another process holds it; the lock goes when this process ends, however it
    ends), installs the SIGINT and SIGTERM handlers and starts the clock. Leaving puts the old handlers back.
    """

    def __init__(self, run_dir: Path | str, cap_s: float, dump: Callable[[Any, Path], None] = _json_dump,
                 load: Callable[[Path], Any] = _json_load, clock: Callable[[], float] = time.time):
        if not cap_s > 0:
            raise ValueError(f"cap_s must be above 0 (seconds; math.inf for no cap), got {cap_s!r}")
        self.run_dir = Path(run_dir)
        self.cap_s = float(cap_s)
        self.dump, self.load, self.clock = dump, load, clock
        self.stop_signal: int | None = None       # the signal that asked for a stop
        self.nonfinite: str | None = None         # where the first non-finite value was seen
        self._carried_s = 0.0                     # effective seconds used before this launch (from the checkpoint)
        self._started_s = math.nan
        self._own_pids = frozenset({os.getpid()})  # a pause counts only if it stopped this process (L07-C1)
        self._saved_here = False
        self._lock = None
        self._previous: dict[int, Any] = {}

    # ------------------------------------------------------------------------------------------ enter and leave
    def __enter__(self) -> "RunGuard":
        self.run_dir.mkdir(parents=True, exist_ok=True)
        lock = open(self.run_dir / LOCK_NAME, "a")
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.close()
            raise RunBusyError(f"another process is already running in the run folder {self.run_dir}") from None
        self._lock = lock
        for number in _STOP_SIGNALS:
            self._previous[number] = signal.signal(number, self._on_signal)
        self._started_s = self.clock()
        return self

    def __exit__(self, *exc: Any) -> None:
        for number, handler in self._previous.items():
            signal.signal(number, handler)
        self._previous = {}
        self._lock.close()
        self._lock = None

    def _on_signal(self, number: int, frame: Any) -> None:
        self.stop_signal = number

    # ------------------------------------------------------------------------------------------ stop: signal or cap
    @property
    def stop_requested(self) -> bool:
        """True once SIGINT or SIGTERM has arrived."""
        return self.stop_signal is not None

    def effective_s(self) -> float:
        """Effective seconds the run folder has used: those carried by the checkpoint this launch resumed from, plus
        this launch's wall clock less the time inside it that a pause had stopped this process."""
        return self._carried_s + pauses.effective_seconds(self._started_s, self.clock(), self._own_pids)

    def cap_reached(self) -> bool:
        return self.effective_s() >= self.cap_s

    def stop_reason(self) -> str | None:
        """:data:`STOP_INTERRUPTED` if a stop was asked for, else :data:`STOP_CAP` at the cap, else None. Ask at every
        step boundary; on a reason, save and return ``EXIT_FOR_STOP[reason]``."""
        if self.stop_requested:
            return STOP_INTERRUPTED
        return STOP_CAP if self.cap_reached() else None

    # ------------------------------------------------------------------------------------------ non-finite values
    def check_finite(self, **values: Any) -> None:
        """Raise :class:`NonFiniteError` if any number in ``values`` (numbers; lists, tuples and dicts of numbers,
        nested) is a NaN or an infinity. From then on this guard saves nothing: the trainer's state may already be
        spoilt, and the last good checkpoint must stay. Pass tensors as numbers (``float(loss)``)."""
        for name, value in values.items():
            found = _first_non_finite(value, name)
            if found is not None:
                self.nonfinite = self.nonfinite or found
                raise NonFiniteError(f"non-finite value at {found}")

    # ------------------------------------------------------------------------------------------ checkpoints
    def save(self, step: int, state: Any) -> None:
        """Write the checkpoint ``{step, state, effective seconds used}`` atomically (``ste/atomic.py``): a crash while
        saving leaves the previous checkpoint. Then ``progress.json`` with the same step and effective seconds (a
        crash between the two leaves it one checkpoint behind, never ahead). The numbers of ``state`` are checked first; a non-finite one, now or
        earlier in this launch, raises :class:`NonFiniteError` and nothing is written."""
        if self.nonfinite is not None:
            raise NonFiniteError(f"a non-finite value was seen ({self.nonfinite}): nothing is saved, the last good "
                                 f"checkpoint is kept")
        self.check_finite(state=state)
        path = self.run_dir / CHECKPOINT_NAME
        temporary = atomic.temporary_path(path)
        payload = {"step": step, "effective_s": self.effective_s(), "saved": self.clock(), "state": state}
        try:
            self.dump(payload, temporary)
            atomic.commit(temporary, path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        self._saved_here = True
        self._note_progress(step, payload["effective_s"], payload["saved"])

    def _note_progress(self, step: Any, effective_s: float, saved_s: float) -> None:
        """Write ``progress.json`` for the waiter. It is a note: a step JSON cannot hold (a PyTorch or NumPy integer)
        is written as an int, one with no int value as null, and a failed write is said on stderr, never raised (the
        waiter then judges the launch alone, the rule before L07-I4)."""
        try:
            step = int(step)
        except (TypeError, ValueError):
            step = None
        try:
            atomic.write_text(self.run_dir / PROGRESS_NAME,
                              json.dumps({"step": step, "effective_s": effective_s, "saved": saved_s}) + "\n")
        except Exception as err:
            print(f"[run guard] {PROGRESS_NAME} not written ({type(err).__name__}: {err}); the checkpoint is saved",
                  file=sys.stderr, flush=True)

    def load_latest(self) -> Checkpoint | None:
        """The latest checkpoint of the run folder, or None on a fresh one. Call it once, before the first step: the
        effective seconds it carries are counted against the cap from then on."""
        path = self.run_dir / CHECKPOINT_NAME
        if not path.exists():
            return None
        payload = self.load(path)
        found = Checkpoint(step=payload["step"], state=payload["state"], effective_s=float(payload["effective_s"]))
        if not self._saved_here:
            self._carried_s = found.effective_s
        return found
