"""Whole-file writes that a crash cannot tear (STE learning track, task L0.7). Linux only; standard library only.

A file is written under a temporary name in the SAME folder, synced to the disk, then renamed over the target
(``os.replace``: on one file system the rename is atomic) and the folder is synced. A reader therefore sees the old
file or the new one, never half of either; a process killed in between leaves the old file whole and a stray
``<name>.tmp.<pid>`` beside it, which nothing reads.
"""
from __future__ import annotations

import os
from pathlib import Path


def temporary_path(path: Path | str) -> Path:
    """The temporary name this process uses for ``path``: same folder, ``<name>.tmp.<pid>``."""
    path = Path(path)
    return path.with_name(f"{path.name}.tmp.{os.getpid()}")


def sync_folder(folder: Path | str) -> None:
    """Make a rename inside ``folder`` survive a power cut."""
    handle = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


def commit(temporary: Path | str, path: Path | str) -> None:
    """Sync the finished file ``temporary`` and rename it over ``path`` (both in one folder)."""
    with open(temporary, "rb") as stream:
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_folder(Path(path).parent)


def write_text(path: Path | str, text: str) -> None:
    """Replace ``path`` by a file holding ``text``, atomically; the folder is made if missing. If the write fails in
    this process the temporary file is removed and the old ``path`` is untouched."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_path(path)
    try:
        temporary.write_text(text)
        commit(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
