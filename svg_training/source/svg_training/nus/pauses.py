"""Pauses of the GPU jobs (owner, 18 Nov 2026: the owner also games on this PC and must be able to pause the runs).

``scripts/gpu_pause.sh pause`` sends SIGSTOP to every svg_training and NUS GPU job and ``resume`` sends SIGCONT; each appends one JSON
line ``{"event": "pause" | "resume" | "stop", "time": <unix seconds>, ...}`` to ``runs/nus_port/phase5/pauses.log``. A paused job keeps
its GPU memory but uses no GPU compute, so a paused interval is neither GPU time nor wall clock against a cap:

* :func:`paused_intervals` - the paused intervals of the log (an unmatched pause runs to ``now``);
* :func:`effective_seconds` - wall clock between two times less the paused time inside it (the elapsed time every hard cap uses);
* :func:`logged_gpu_hours` - GPU-hours of one stage group in a ``gpu_hours.log``: the union of its CUDA intervals (overlapping jobs
  counted once) less the paused time inside them.

Pure standard library; no numeric literal other than 0, 1, -1, 2 (G2).
"""
from __future__ import annotations

import datetime
import json
import time
from pathlib import Path

from .rules import ROOT

PAUSES_LOG = ROOT / "runs" / "nus_port" / "phase5" / "pauses.log"
HOUR_S = datetime.timedelta(hours=1).total_seconds()


def _rows(path: Path | str) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def union(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Merged, sorted intervals (overlapping or touching intervals become one)."""
    out: list[list[float]] = []
    for start, end in sorted(intervals):
        if out and start <= out[-1][1]:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return [(a, b) for a, b in out]


def paused_intervals(path: Path | str = PAUSES_LOG, now: float | None = None) -> list[tuple[float, float]]:
    """(start, end) of every paused interval: a "pause" opens one, the next "resume" or "stop" closes it; an open one ends at ``now``."""
    now = time.time() if now is None else now
    spans, opened = [], None
    for row in sorted(_rows(path), key=lambda r: r["time"]):
        if row["event"] == "pause" and opened is None:
            opened = float(row["time"])
        elif row["event"] in ("resume", "stop") and opened is not None:
            spans.append((opened, float(row["time"])))
            opened = None
    if opened is not None:
        spans.append((opened, max(now, opened)))
    return union(spans)


def overlap(span: tuple[float, float], intervals: list[tuple[float, float]]) -> float:
    start, end = span
    return sum(max(0.0, min(end, b) - max(start, a)) for a, b in intervals)


def effective_seconds(start: float, end: float, path: Path | str = PAUSES_LOG) -> float:
    """Wall clock from ``start`` to ``end`` (unix seconds) less the paused time inside it."""
    return (end - start) - overlap((start, end), paused_intervals(path, now=end))


def logged_gpu_hours(log: Path | str, group: str, pauses: Path | str = PAUSES_LOG) -> float:
    """GPU-hours of one stage group: the union of its CUDA intervals less the paused time inside them."""
    spans = union([(float(r["start"]), float(r["end"])) for r in _rows(log)
                   if r["group"] == group and str(r["device"]).startswith("cuda")])
    paused = paused_intervals(pauses)
    return sum((b - a) - overlap((a, b), paused) for a, b in spans) / HOUR_S


def append_row(log: Path | str, row: dict) -> None:
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as stream:
        stream.write(json.dumps(row) + "\n")
