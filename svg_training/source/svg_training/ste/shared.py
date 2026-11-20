"""The one machine-wide folder of live process state (STE learning track, task L0.7). Linux only.

GPU jobs are launched from many worktrees of one repository, and the owner pauses them with whichever copy of
``scripts/gpu_pause.sh`` is at hand. Whatever every worktree must see (the pause log, ``state.json``, the GPU-hour
ledger) therefore lives in ONE folder, the same from every worktree:

* ``SVG_SHARED_DIR`` if it is set (tests point it at a temporary folder; a container without git must set it);
* otherwise ``<main clone>/svg_training/runs/shared``. The main clone is the parent of git's common folder
  (``git rev-parse --git-common-dir``), asked from this package's own location. Git prints that folder as a relative
  ``.git`` inside the main clone and as an absolute path inside a worktree; both are resolved against the folder asked.

``runs/`` is git-ignored, so nothing here is ever committed. The folder is created on demand.

Old copies of ``gpu_pause.sh`` (other worktrees, older branches) write only their own
``<worktree>/svg_training/runs/nus_port/phase5/pauses.log``; :func:`legacy_pause_logs` lists that path for every
worktree of the repository, so the pause reader (``ste/pauses.py``) can merge them. ``SVG_PAUSE_LEGACY_LOGS`` replaces
that list (paths joined by ``os.pathsep``; empty = none).

Nothing is looked up at import time. Git's answers are cached for the life of the process: a worktree added while a
job runs is seen by the next process, not by the running one. Standard library only.
"""
from __future__ import annotations

import functools
import os
import subprocess
from pathlib import Path

SHARED_ENV = "SVG_SHARED_DIR"
LEGACY_LOGS_ENV = "SVG_PAUSE_LEGACY_LOGS"
PACKAGE_DIR = Path(__file__).resolve().parent
SHARED_REL = Path("svg_training", "runs", "shared")                           # under the main clone
LEGACY_PAUSE_REL = Path("svg_training", "runs", "nus_port", "phase5", "pauses.log")   # under each worktree
PAUSES_LOG_NAME = "pauses.log"
STATE_NAME = "state.json"
STATE_LOCK_NAME = "state.lock"
GPU_HOURS_LOG_NAME = "gpu_hours.log"
_GIT_TIMEOUT_S = 30.0
_WORKTREE_PREFIX = "worktree "


class SharedDirError(RuntimeError):
    """The shared folder cannot be found: not inside a git repository (or no git) and ``SVG_SHARED_DIR`` not set."""


@functools.lru_cache(maxsize=None)
def _git(start: Path, *args: str) -> str:
    try:
        done = subprocess.run(["git", "-C", str(start), *args], capture_output=True, text=True, timeout=_GIT_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as err:
        raise SharedDirError(f"git could not be run from {start} ({err}); set {SHARED_ENV} to the shared folder") from err
    if done.returncode != 0:
        raise SharedDirError(f"{start} is not inside a git repository ({done.stderr.strip()}); set {SHARED_ENV} to the "
                             f"shared folder")
    return done.stdout


def main_clone(start: Path | str = PACKAGE_DIR) -> Path:
    """The repository's main clone (the folder that holds the real ``.git``), asked from the folder ``start``."""
    start = Path(start)
    common = _git(start, "rev-parse", "--git-common-dir").strip()
    return (start / common).resolve().parent              # ``.git`` in the main clone, an absolute path in a worktree


def worktrees(start: Path | str = PACKAGE_DIR) -> tuple[Path, ...]:
    """Every worktree of the repository, the main clone included (``git worktree list``)."""
    lines = _git(Path(start), "worktree", "list", "--porcelain").splitlines()
    return tuple(Path(line[len(_WORKTREE_PREFIX):]) for line in lines if line.startswith(_WORKTREE_PREFIX))


def shared_dir(create: bool = True, start: Path | str = PACKAGE_DIR) -> Path:
    """The shared folder; made if missing unless ``create`` is false."""
    named = os.environ.get(SHARED_ENV)
    folder = Path(named) if named else main_clone(start) / SHARED_REL
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def pauses_log() -> Path:
    """The one pause log: every pause, resume and stop of ``scripts/gpu_pause.sh``, one JSON line each."""
    return shared_dir() / PAUSES_LOG_NAME


def state_file() -> Path:
    """``state.json``: the live jobs and task states (``ste/state.py``)."""
    return shared_dir() / STATE_NAME


def state_lock() -> Path:
    """The lock file every writer of ``state.json`` holds exclusively while it writes."""
    return shared_dir() / STATE_LOCK_NAME


def gpu_hours_log() -> Path:
    """The GPU-hour ledger: one JSON line per CUDA interval of a job (``ste/budget.py``); append-only."""
    return shared_dir() / GPU_HOURS_LOG_NAME


def legacy_pause_logs(start: Path | str = PACKAGE_DIR) -> tuple[Path, ...]:
    """Where old copies of ``gpu_pause.sh`` write: one path per worktree (the file may not exist), or the paths of
    ``SVG_PAUSE_LEGACY_LOGS`` when that variable is set."""
    named = os.environ.get(LEGACY_LOGS_ENV)
    if named is not None:
        return tuple(Path(part) for part in named.split(os.pathsep) if part)
    try:
        return tuple(tree / LEGACY_PAUSE_REL for tree in worktrees(start))
    except SharedDirError as err:
        raise SharedDirError(f"{err}; and set {LEGACY_LOGS_ENV} to the legacy pause logs to read (empty for none)") from err
