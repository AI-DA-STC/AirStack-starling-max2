"""The partner's opponent selection and batch shape (NUS port Phase 5, task M4), described from
``ma_skills/runner/ensemble_self_play_runner.py`` (``select_opponents`` :29-43, ``_start_generation`` :183-226). Pure and import-light, so
N0's 5.1-b pool (``nus/crossplay.py``) can use it. Holds no partner value (G2).

* The pool of generation g holds the archived entries of the other team. If there are at most ``maximum`` of them, all are kept;
  otherwise the latest ``recent`` are kept plus ``maximum - recent`` older ones drawn without replacement with NumPy's generator seeded
  by (run seed, generation) - the same NumPy call as the partner's, so the selection is identical for an identical archive - and the
  pool is sorted by generation.
* Games per update: slots x max(games per opponent, ceil(minimum batch / slots)), slots = learned opponents + the scripted one.
* Stage seed of generation g: run seed + g - 1.
"""
from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np


def select_opponents(archive: Sequence[dict[str, Any]], *, team: str, generation: int, seed: int, maximum: int,
                     recent: int) -> list[dict[str, Any]]:
    """The learned opponents of ``team``'s learner in ``generation``: entries (dicts with ``generation`` and ``team``) of the other team."""
    if not 0 <= recent <= maximum or maximum < 1:
        raise ValueError("require 0 <= recent <= maximum and maximum >= 1")
    history = sorted((e for e in archive if e["team"] != team), key=lambda e: e["generation"])
    if len(history) <= maximum:
        return list(history)
    split = len(history) - recent                      # entries before ``split`` are drawn from, the rest are kept
    kept = history[split:]
    stream = np.random.default_rng(np.random.SeedSequence([int(seed), int(generation)]))
    picks = stream.choice(split, maximum - recent, replace=False).tolist()
    chosen = [history[k] for k in picks]
    return sorted(chosen + kept, key=lambda e: e["generation"])


def rollout_batch_size(slots: int, games_per_opponent: int, minimum_batch: int) -> int:
    """Games per update for ``slots`` pool slots (learned plus scripted), in equal blocks."""
    if slots < 1:
        raise ValueError("at least one slot")
    return slots * max(games_per_opponent, math.ceil(minimum_batch / slots))


def stage_seed(seed: int, generation: int) -> int:
    return int(seed) + int(generation) - 1
