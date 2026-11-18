"""The ``--device`` choice of the command-line scripts (docs panel C1/C2, owner 18 Nov 2026).

``auto`` (the default of ``scripts/score.py`` and ``scripts/train_standin.py``) means CUDA when PyTorch sees a GPU, else the CPU, with
one note on stderr so a CPU run is never silent. An explicit device (``cpu``, ``cuda``, ``cuda:1``) is kept as given.
"""
from __future__ import annotations

import sys

AUTO = "auto"


def resolve_device(requested: str) -> str:
    """``auto`` -> ``cuda`` if ``torch.cuda.is_available()`` else ``cpu`` (with a note on stderr); anything else unchanged."""
    if requested != AUTO:
        return requested
    import torch

    if torch.cuda.is_available():
        return "cuda"
    print("note: --device auto: no CUDA GPU visible to PyTorch, running on the cpu (slower; give --device cuda to require a GPU)",
          file=sys.stderr)
    return "cpu"
