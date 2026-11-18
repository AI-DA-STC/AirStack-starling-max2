"""Pause accounting (nus/pauses.py; owner, 18 Nov 2026): paused intervals from the pause log, wall clock less pauses for every hard cap,
and GPU-hours less pauses."""
import pytest

from _nus_phase5_method_fixture import (EFFECTIVE_CASE, GPU_HOURS_AFTER_PAUSES, GPU_PAUSES, GPU_ROWS, PAUSE_EVENTS, PAUSE_NOW,
                                        PAUSED_SPANS)
from svg_training.nus import pauses as P


def _log(path, events):
    for event, t in events:
        P.append_row(path, {"event": event, "time": t})


def test_paused_intervals_and_effective_time(tmp_path):
    log = tmp_path / "pauses.log"
    assert P.paused_intervals(log, now=PAUSE_NOW) == []
    _log(log, PAUSE_EVENTS)
    assert P.paused_intervals(log, now=PAUSE_NOW) == PAUSED_SPANS
    start, end, expected = EFFECTIVE_CASE
    assert P.effective_seconds(start, end, log) == pytest.approx(expected)


def test_gpu_hours_less_pauses(tmp_path):
    rows, pauses = tmp_path / "gpu_hours.log", tmp_path / "pauses.log"
    for group, device, start, end in GPU_ROWS:
        P.append_row(rows, {"group": group, "device": device, "start": start, "end": end})
    _log(pauses, GPU_PAUSES)
    assert P.logged_gpu_hours(rows, "s51", pauses) == pytest.approx(GPU_HOURS_AFTER_PAUSES)
    assert P.logged_gpu_hours(rows, "other", pauses) == 0
