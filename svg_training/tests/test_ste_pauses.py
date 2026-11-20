"""STE learning track, task L0.7: paused time for cap accounting (ste/pauses.py).

The owner pauses GPU jobs with whichever copy of ``scripts/gpu_pause.sh`` is at hand. New copies write the shared log
and their own legacy log; old copies (other worktrees) write only their legacy log. The reader merges the EVENTS of
every log, counts an event that is in two logs once, and hands the merged log to ``nus/pauses.py`` (imported, not
copied) for the interval arithmetic. Failure F-e of 20 Nov 2026: paused time must not count against a cap whichever
copy made the pause."""
import json
import math
import os
import subprocess
import uuid
from pathlib import Path

import pytest

from _ste_tools import LEGACY_REL, SOURCE, pause_script
from _proc import child_env, child_python
from svg_training.nus import pauses as nus_pauses
from svg_training.ste import pauses, shared

T0 = 1_000_000.0          # made-up clock, seconds


def write(log: Path, events: list[tuple[str, float]], pids: tuple[int, ...] = (7,)) -> None:
    """Append events in the exact line format of gpu_pause.sh."""
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as stream:
        for event, time_s in events:
            stream.write(json.dumps({"event": event, "time": time_s, "pids": list(pids), "by": "tester"}) + "\n")


@pytest.fixture()
def logs(tmp_path, monkeypatch):
    """The shared log and the legacy logs of two made-up worktrees; the boot is long before every made-up event."""
    shared_dir = tmp_path / "shared"
    legacy = (tmp_path / "wt_old" / LEGACY_REL, tmp_path / "wt_new" / LEGACY_REL)
    monkeypatch.setenv(shared.SHARED_ENV, str(shared_dir))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, os.pathsep.join(map(str, legacy)))
    monkeypatch.setattr(pauses, "boot_time_s", lambda: 0.0)
    return shared_dir / "pauses.log", legacy[0], legacy[1]


def test_no_log_no_pause(logs):
    assert pauses.pause_logs() == logs
    assert pauses.pause_events() == [] and pauses.paused_intervals(now=T0) == []
    assert pauses.effective_seconds(T0, T0 + 100.0) == 100.0


def test_pause_resume_pairs_and_a_stop_closes_a_pause(logs):
    shared_log, _, _ = logs
    write(shared_log, [("pause", T0 + 10), ("resume", T0 + 25), ("pause", T0 + 40), ("stop", T0 + 70), ("resume", T0 + 80)])
    assert pauses.paused_intervals(now=T0 + 500) == [(T0 + 10, T0 + 25), (T0 + 40, T0 + 70)]
    assert pauses.paused_seconds(T0, T0 + 100) == 45.0


def test_an_unmatched_pause_runs_to_now(logs):
    shared_log, _, _ = logs
    write(shared_log, [("pause", T0 + 10), ("resume", T0 + 20), ("pause", T0 + 50)])
    assert pauses.paused_intervals(now=T0 + 90) == [(T0 + 10, T0 + 20), (T0 + 50, T0 + 90)]
    assert pauses.paused_intervals(now=T0 + 300) == [(T0 + 10, T0 + 20), (T0 + 50, T0 + 300)]     # same log, later clock
    assert pauses.effective_seconds(T0, T0 + 300) == 300.0 - 10.0 - 250.0


def test_effective_seconds_across_a_pause(logs):
    """A job from T0 to T0+100 paused from +30 to +70 did 60 s of work; a window inside the pause did none."""
    shared_log, _, _ = logs
    write(shared_log, [("pause", T0 + 30), ("resume", T0 + 70)])
    assert pauses.effective_seconds(T0, T0 + 100) == 60.0
    assert pauses.effective_seconds(T0 + 40, T0 + 60) == 0.0
    assert pauses.effective_seconds(T0 + 50, T0 + 100) == 30.0
    assert pauses.effective_seconds(T0 + 80, T0 + 100) == 20.0


def test_an_event_in_two_logs_is_counted_once(logs):
    """A new copy writes the same line to the shared log and to its legacy log."""
    shared_log, _, legacy_new = logs
    for log in (shared_log, legacy_new):
        write(log, [("pause", T0 + 10), ("resume", T0 + 30), ("pause", T0 + 50), ("resume", T0 + 60)])
    assert [e["event"] for e in pauses.pause_events()] == ["pause", "resume", "pause", "resume"]
    assert pauses.paused_intervals(now=T0 + 100) == [(T0 + 10, T0 + 30), (T0 + 50, T0 + 60)]
    assert pauses.paused_seconds(T0, T0 + 100) == 30.0


def test_f_e_a_pause_made_by_an_old_copy_in_another_worktree_is_counted(logs):
    """F-e: the old copy writes only ``<its worktree>/svg_training/runs/nus_port/phase5/pauses.log``. Reading the
    shared log alone (the reproduction) counts the paused hour against the cap; the merged reader does not."""
    shared_log, legacy_old, _ = logs
    write(legacy_old, [("pause", T0 + 600), ("resume", T0 + 4200)])
    write(shared_log, [("pause", T0 + 5000), ("resume", T0 + 5100)])
    assert nus_pauses.effective_seconds(T0, T0 + 7200, shared_log) == 7100.0      # the failure: one log misses the hour
    assert pauses.effective_seconds(T0, T0 + 7200) == 3500.0                      # caught: 7200 - 3600 - 100
    assert pauses.paused_intervals(now=T0 + 7200) == [(T0 + 600, T0 + 4200), (T0 + 5000, T0 + 5100)]


def test_a_pause_by_one_copy_and_the_resume_by_another_pair_up(logs):
    """Events are merged before they are paired: per-log pairing would leave the old copy's pause open for ever, and
    no cap would fire again."""
    shared_log, legacy_old, legacy_new = logs
    write(legacy_old, [("pause", T0 + 10)])
    for log in (shared_log, legacy_new):
        write(log, [("resume", T0 + 40)])
    assert pauses.paused_intervals(now=T0 + 1000) == [(T0 + 10, T0 + 40)]
    assert nus_pauses.paused_intervals(legacy_old, now=T0 + 1000) == [(T0 + 10, T0 + 1000)]      # that log alone


def test_same_arithmetic_as_the_nus_module_on_one_log(logs):
    shared_log, _, _ = logs
    events = [("pause", T0 + 5), ("pause", T0 + 6), ("resume", T0 + 9), ("resume", T0 + 12), ("stop", T0 + 13),
              ("pause", T0 + 20), ("stop", T0 + 21), ("pause", T0 + 21), ("resume", T0 + 30), ("pause", T0 + 44)]
    write(shared_log, events)
    for now in (T0, T0 + 20.5, T0 + 44, T0 + 50, T0 + 1e6):
        assert pauses.paused_intervals(now=now) == nus_pauses.paused_intervals(shared_log, now=now)
    for start, end in ((T0, T0 + 50), (T0 + 7, T0 + 25), (T0 + 44, T0 + 45)):
        assert pauses.effective_seconds(start, end) == nus_pauses.effective_seconds(start, end, shared_log)


def test_a_new_event_is_seen_by_the_next_read(logs):
    """The merged log is kept between reads (a trainer asks at every step) and rebuilt when any log changes."""
    shared_log, legacy_old, _ = logs
    write(shared_log, [("pause", T0 + 10)])
    assert pauses.paused_intervals(now=T0 + 50) == [(T0 + 10, T0 + 50)]
    write(shared_log, [("resume", T0 + 20)])
    assert pauses.paused_intervals(now=T0 + 50) == [(T0 + 10, T0 + 20)]
    write(legacy_old, [("pause", T0 + 30), ("resume", T0 + 35)])                   # a log that did not exist before
    assert pauses.paused_intervals(now=T0 + 50) == [(T0 + 10, T0 + 20), (T0 + 30, T0 + 35)]
    assert pauses.merges_done() >= 3
    before = pauses.merges_done()
    for _ in range(50):
        pauses.effective_seconds(T0, T0 + 50)
    assert pauses.merges_done() == before                                          # nothing changed: nothing re-read


def test_a_pause_left_open_by_a_reboot_ends_at_the_boot(logs, monkeypatch):
    """A power cut during an owner pause: nothing is paused after the boot. Without this rule the pause would run to
    "now" for ever and no cap would fire again (AUTOMATION section 2.3)."""
    shared_log, _, _ = logs
    write(shared_log, [("pause", T0 + 10), ("resume", T0 + 20), ("pause", T0 + 100)])
    monkeypatch.setattr(pauses, "boot_time_s", lambda: T0 + 500.0)
    assert pauses.paused_intervals(now=T0 + 900) == [(T0 + 10, T0 + 20), (T0 + 100, T0 + 500)]
    last = pauses.pause_events()[-1]
    assert (last["event"], last["time"], last["synthetic"]) == ("resume", T0 + 500.0, True)
    assert pauses.effective_seconds(T0 + 600, T0 + 900) == 300.0                   # a job relaunched after the boot


def test_a_pause_made_in_this_boot_stays_open(logs, monkeypatch):
    shared_log, _, _ = logs
    monkeypatch.setattr(pauses, "boot_time_s", lambda: T0 + 50.0)
    write(shared_log, [("pause", T0 + 100)])
    assert pauses.paused_intervals(now=T0 + 900) == [(T0 + 100, T0 + 900)]
    assert all("synthetic" not in event for event in pauses.pause_events())


def test_boot_time_is_this_machines(monkeypatch):
    import time
    assert 0.0 < pauses.boot_time_s() < time.time()


def test_a_torn_line_is_skipped_and_reported(logs, capsys):
    """A power cut can leave half a line at the end of a log: the other events still count."""
    shared_log, _, _ = logs
    write(shared_log, [("pause", T0 + 10), ("resume", T0 + 20)])
    with shared_log.open("a") as stream:
        stream.write('{"event": "pause", "ti')
    assert pauses.paused_intervals(now=T0 + 50) == [(T0 + 10, T0 + 20)]
    assert "1 unreadable line" in capsys.readouterr().err


def test_explicit_logs_replace_the_default_list(logs, tmp_path):
    other = tmp_path / "elsewhere.log"
    write(other, [("pause", T0 + 1), ("resume", T0 + 3)])
    assert pauses.paused_intervals(now=T0 + 9) == []
    assert pauses.paused_intervals(now=T0 + 9, logs=[other]) == [(T0 + 1, T0 + 3)]
    assert pauses.effective_seconds(T0, T0 + 9, logs=[other]) == 7.0


def test_with_the_real_script_new_copy_and_old_copy(tmp_path, monkeypatch):
    """End to end with scripts/gpu_pause.sh: a new copy (run from a made-up worktree) writes both logs and is counted
    once; an old copy is stood in for by a run whose shared folder is somewhere the reader never looks."""
    shared_dir = tmp_path / "shared"
    legacy_new, legacy_old = tmp_path / "wt_new" / LEGACY_REL, tmp_path / "wt_old" / LEGACY_REL
    nothing = f"no_such_{uuid.uuid4().hex}"
    pause_script("pause", tmp_path, shared_dir, nothing, legacy_new)
    pause_script("resume", tmp_path, shared_dir, nothing, legacy_new)
    pause_script("pause", tmp_path, tmp_path / "unseen", nothing, legacy_old)     # the old copy knows no shared folder
    pause_script("resume", tmp_path, tmp_path / "unseen", nothing, legacy_old)
    monkeypatch.setenv(shared.SHARED_ENV, str(shared_dir))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, os.pathsep.join(map(str, (legacy_new, legacy_old))))
    events = pauses.pause_events()
    assert [e["event"] for e in events] == ["pause", "resume", "pause", "resume"]
    spans = pauses.paused_intervals()
    assert len(spans) == 2 and all(end > start for start, end in spans)
    assert len((shared_dir / "pauses.log").read_text().splitlines()) == 2
    assert math.isclose(pauses.paused_seconds(spans[0][0], spans[1][1]), sum(end - start for start, end in spans))


def test_importing_loads_no_pytorch():
    code = "import sys\nimport svg_training.ste.pauses\nassert 'torch' not in sys.modules and 'numpy' not in sys.modules\n"
    done = subprocess.run([child_python(), "-c", code], env=child_env(str(SOURCE)), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
