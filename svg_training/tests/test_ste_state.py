"""STE learning track, task L0.7: the live state file ``<shared folder>/state.json`` (ste/state.py, ste/atomic.py).

Every write holds an exclusive lock, writes a temporary file in the same folder, syncs it and renames it over the old
file. A job is alive only if its pid exists AND that process started when the record says AND the record was made in
this boot: a pid reused by another program, or a record left by a power cut (failure F-d of 20 Nov 2026), reads as
dead, never as alive."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from _ste_tools import SOURCE, WAIT_S, reap, tool_env, wait_for
from _proc import child_env, child_python
from svg_training.ste import atomic, shared, state

OTHER_BOOT = "00000000-0000-4000-8000-000000000000"


@pytest.fixture(autouse=True)
def own_shared_folder(tmp_path, monkeypatch):
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    return tmp_path / "shared"


def job_of(pid: int, **changes) -> dict:
    """A complete job record for the live process ``pid``."""
    job = {"task": "L0.7", "pid": pid, "pid_start": state.process_start_time(pid), "boot_id": state.boot_id(),
           "cmd": ["python", "x.py"], "cwd": "/tmp", "run_dir": "/tmp/run", "log": "/tmp/run/job.log",
           "started": 1.0, "expected_min_s": 60.0, "gpu_h": 0.0, "launch": 1, "child_pid": None, "child_start": None,
           "exit_code": None, "ended": None}
    job.update(changes)
    return job


def sleeper() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", "import time\nwhile True: time.sleep(0.05)"])


# ------------------------------------------------------------------------------------------------ read and write
def test_a_missing_file_reads_as_an_empty_state_and_is_not_created(own_shared_folder):
    fresh = state.read()
    assert fresh == {"schema": state.SCHEMA, "updated": None, "boot_id": None, "phase": None, "tasks": {}, "jobs": {}}
    assert state.SCHEMA == 1 and not shared.state_file().exists()


def test_update_writes_under_the_lock_and_read_returns_it(own_shared_folder):
    def change(data: dict) -> None:
        data["phase"] = "L0"
        data["tasks"]["L0.7"] = {"state": "building", "attempts": 0}
        data["jobs"]["dummy"] = job_of(os.getpid())

    written = state.update(change)
    assert shared.state_file() == own_shared_folder / "state.json" and shared.state_lock().exists()
    on_disk = json.loads(shared.state_file().read_text())
    assert on_disk == written == state.read()
    assert on_disk["schema"] == 1 and on_disk["phase"] == "L0" and on_disk["boot_id"] == state.boot_id()
    assert on_disk["updated"].endswith("+00:00") and on_disk["jobs"]["dummy"]["pid"] == os.getpid()
    assert sorted(p.name for p in own_shared_folder.iterdir()) == ["state.json", "state.lock"]       # no temp file left


def test_a_change_that_raises_writes_nothing(own_shared_folder):
    state.update(lambda data: data["tasks"].update({"L0.7": {"state": "queued", "attempts": 0}}))
    before = shared.state_file().read_bytes()

    def bad(data: dict) -> None:
        data["tasks"]["L0.7"]["attempts"] = 5
        raise RuntimeError("stop")

    with pytest.raises(RuntimeError, match="stop"):
        state.update(bad)
    assert shared.state_file().read_bytes() == before


@pytest.mark.parametrize("text, message", [
    ('{"schema": 2, "updated": null, "boot_id": null, "phase": null, "tasks": {}, "jobs": {}}', "schema version 2"),
    ('{"updated": null, "boot_id": null, "phase": null, "tasks": {}, "jobs": {}}', "schema version None"),
    ("{not json", "not valid JSON"),
    ("[1, 2]", "must be a JSON object"),
    ('{"schema": 1, "updated": null, "boot_id": null, "phase": null, "tasks": {}, "jobs": {}, "extra": 1}', "extra"),
    ('{"schema": 1, "updated": null, "boot_id": null, "phase": null, "tasks": {}}', "jobs"),
    ('{"schema": 1, "updated": null, "boot_id": null, "phase": null, "tasks": {"L0.7": {"state": "flying", "attempts": 0}}, "jobs": {}}',
     "flying"),
    ('{"schema": 1, "updated": null, "boot_id": null, "phase": null, "tasks": {}, "jobs": {"a": {"pid": 3}}}', "job 'a'"),
])
def test_an_unknown_schema_version_or_a_malformed_file_raises(own_shared_folder, text, message):
    own_shared_folder.mkdir()
    shared.state_file().write_text(text)
    with pytest.raises(state.StateError, match=message):
        state.read()
    with pytest.raises(state.StateError, match=message):
        state.update(lambda data: None)                                   # and it is never overwritten
    assert shared.state_file().read_text() == text


def test_a_malformed_record_is_refused_before_it_is_written(own_shared_folder):
    state.update(lambda data: data["jobs"].update({"good": job_of(os.getpid())}))
    before = shared.state_file().read_bytes()
    incomplete = job_of(os.getpid())
    del incomplete["boot_id"]
    for bad in (incomplete, job_of(os.getpid(), surprise=1), job_of("12"), job_of(os.getpid(), cmd="python x.py")):
        with pytest.raises(state.StateError):
            state.update(lambda data: data["jobs"].update({"bad": bad}))
    with pytest.raises(state.StateError, match="attempts"):
        state.update(lambda data: data["tasks"].update({"L0.7": {"state": "queued"}}))
    assert shared.state_file().read_bytes() == before
    assert "gate-written" in state.TASK_STATES and "blocked-on-human" in state.TASK_STATES


# ------------------------------------------------------------------------------------------------ concurrency, crashes
WRITER = """
import sys
from svg_training.ste import state
def bump(data):
    task = data["tasks"].setdefault("L0.7", {"state": "building", "attempts": 0})
    task["attempts"] += 1
for _ in range(int(sys.argv[1])):
    state.update(bump)
"""


def test_processes_updating_at_once_lose_no_update(own_shared_folder):
    writers, each = 4, 25
    env = tool_env(own_shared_folder)
    procs = [subprocess.Popen([child_python(), "-c", WRITER, str(each)], env=env, stderr=subprocess.PIPE)
             for _ in range(writers)]
    try:
        for proc in procs:
            assert proc.wait(timeout=WAIT_S) == 0, proc.stderr.read().decode()
    finally:
        for proc in procs:
            reap(proc)
    assert state.read()["tasks"]["L0.7"]["attempts"] == writers * each
    assert sorted(p.name for p in own_shared_folder.iterdir()) == ["state.json", "state.lock"]


CRASHER = """
import os
from svg_training.ste import atomic, state
def crash(source, target):
    os._exit(9)                      # the process dies after the temporary file is written, before the rename
atomic.os.replace = crash
state.update(lambda data: data["tasks"].update({"L0.7": {"state": "failed", "attempts": 99}}))
"""


def test_a_crash_between_the_temporary_file_and_the_rename_leaves_the_old_file(own_shared_folder):
    state.update(lambda data: data["tasks"].update({"L0.7": {"state": "testing", "attempts": 1}}))
    before = shared.state_file().read_bytes()
    done = subprocess.run([child_python(), "-c", CRASHER], env=tool_env(own_shared_folder), capture_output=True,
                          text=True, timeout=WAIT_S)
    assert done.returncode == 9, done.stderr
    leftovers = [p.name for p in own_shared_folder.iterdir() if p.name not in ("state.json", "state.lock")]
    assert len(leftovers) == 1 and leftovers[0].startswith("state.json.tmp.")      # the crash did happen mid-write
    assert shared.state_file().read_bytes() == before                             # the old file is whole
    assert state.read()["tasks"]["L0.7"] == {"state": "testing", "attempts": 1}
    after = state.update(lambda data: data["tasks"]["L0.7"].update(attempts=2))    # the dead writer's lock is gone
    assert after["tasks"]["L0.7"]["attempts"] == 2


def test_a_failed_rename_in_this_process_leaves_the_old_file_and_no_temporary_file(own_shared_folder, monkeypatch):
    state.update(lambda data: data["tasks"].update({"L0.7": {"state": "testing", "attempts": 1}}))
    before = shared.state_file().read_bytes()

    def refuse(source, target):
        raise OSError("disk says no")

    with monkeypatch.context() as patch:
        patch.setattr(atomic.os, "replace", refuse)
        with pytest.raises(OSError, match="disk says no"):
            state.update(lambda data: data["tasks"]["L0.7"].update(attempts=2))
    assert shared.state_file().read_bytes() == before
    assert sorted(p.name for p in shared.state_file().parent.iterdir()) == ["state.json", "state.lock"]


def test_atomic_write_replaces_whole_files(tmp_path):
    target = tmp_path / "a" / "exit_code"
    atomic.write_text(target, "3\n")
    assert target.read_text() == "3\n"
    atomic.write_text(target, "4\n")
    assert target.read_text() == "4\n" and [p.name for p in target.parent.iterdir()] == ["exit_code"]


# ------------------------------------------------------------------------------------------------ is the job alive?
def test_boot_id_and_start_time_of_this_process():
    assert state.boot_id() == Path("/proc/sys/kernel/random/boot_id").read_text().strip() and len(state.boot_id()) == 36
    started = state.process_start_time(os.getpid())
    assert isinstance(started, int) and started > 0 and started == state.process_start_time(os.getpid())
    assert state.process_state(os.getpid()) == "R"


def test_stat_line_with_brackets_and_spaces_in_the_program_name():
    line = "4242 (my (odd) prog) S 1 4242 4242 0 -1 4194304 100 0 0 0 1 2 0 0 20 0 1 0 987654 1000 10 18446744073709551615"
    assert state.parse_stat(line) == ("S", 987654)


def test_a_live_job_is_alive_and_a_finished_or_unknown_pid_is_dead():
    proc = sleeper()
    try:
        job = job_of(proc.pid)
        assert state.job_alive(job) and state.job_status(job) == state.ALIVE
        os.kill(proc.pid, 19)                                            # SIGSTOP: paused is still alive
        wait_for(lambda: state.process_state(proc.pid) == "T", what="the stop")
        assert state.job_alive(job) and state.job_status(job) == state.ALIVE
        os.kill(proc.pid, 18)
        proc.kill()
        wait_for(lambda: state.process_state(proc.pid) == "Z", what="the zombie")
        # killed but not yet collected by its parent: /proc still shows the pid with the same start time
        assert state.process_start_time(proc.pid) is None
        assert not state.job_alive(job) and state.job_status(job) == state.DEAD
    finally:
        reap(proc)
    assert state.process_start_time(proc.pid) is None and state.process_state(proc.pid) is None
    assert not state.job_alive(job) and state.job_status(job) == state.DEAD


def test_a_reused_pid_is_dead():
    """The pid exists but that process did not start when the record says: another program has the number now."""
    proc = sleeper()
    try:
        true_start = state.process_start_time(proc.pid)
        assert state.job_alive(job_of(proc.pid))
        for other_start in (true_start - 1, true_start + 1, 0):
            job = job_of(proc.pid, pid_start=other_start)
            assert not state.job_alive(job) and state.job_status(job) == state.DEAD
    finally:
        reap(proc)


def test_f_d_a_job_recorded_in_another_boot_is_dead_previous_boot():
    """F-d: after a power cut the pid file is stale. Checking the pid alone (the reproduction) says "alive", because
    some process of the new boot has that number; the record's boot id says the job died with the old boot."""
    proc = sleeper()
    try:
        job = job_of(proc.pid, boot_id=OTHER_BOOT)                       # same pid, even the same start time
        os.kill(job["pid"], 0)                                           # the failure: a pid-only check passes
        assert state.process_start_time(job["pid"]) == job["pid_start"]
        assert not state.job_alive(job)
        assert state.job_status(job) == state.DEAD_PREVIOUS_BOOT == "dead (previous boot)"
    finally:
        reap(proc)


def test_the_job_lives_while_its_command_lives_even_if_the_wrapper_is_gone():
    """The recorded pid is the wrapper's; ``child_pid`` is the command it started. A killed wrapper with the command
    still running is not a dead job: a relaunch then would run two trainers in one run folder."""
    wrapper, child = sleeper(), sleeper()
    try:
        job = job_of(wrapper.pid, child_pid=child.pid, child_start=state.process_start_time(child.pid))
        assert state.job_status(job) == state.ALIVE
        wrapper.kill()
        wrapper.wait()
        assert state.job_alive(job) and state.job_status(job) == state.ALIVE_NO_WRAPPER == "alive (wrapper gone)"
        assert state.job_status(dict(job, boot_id=OTHER_BOOT)) == state.DEAD_PREVIOUS_BOOT
        child.kill()
        child.wait()
        assert not state.job_alive(job) and state.job_status(job) == state.DEAD
    finally:
        reap(wrapper)
        reap(child)


def test_importing_loads_no_pytorch():
    code = ("import sys\nimport svg_training.ste.state, svg_training.ste.atomic\n"
            "assert 'torch' not in sys.modules and 'numpy' not in sys.modules\n")
    done = subprocess.run([child_python(), "-c", code], env=child_env(str(SOURCE)), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
