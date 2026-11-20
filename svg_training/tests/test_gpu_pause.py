"""scripts/gpu_pause.sh (owner, 18 Nov 2026): pause = SIGSTOP, resume = SIGCONT, stop = SIGINT (then SIGCONT, so a paused job receives
it), status lists the jobs; every pause, resume and stop is appended to the pause log. The test runs a dummy Python process whose command
line holds a unique marker and points the script at that marker and a private log, so no real job can be touched.

STE track, task L0.7: the same event line also goes to the one shared pause log (``<shared folder>/pauses.log``, the same from every
worktree), the legacy log and ``GPU_PAUSE_LOG`` work as before, and the default pattern also finds the track's job scripts
(``scripts/ste_*.py``) but never the track's own launcher, wrapper or waiter (``scripts/ste_job.py``)."""
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "gpu_pause.sh"
WAIT_S = 10


def _state(pid: int) -> str:
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]


def _wait(predicate) -> bool:
    end = time.monotonic() + WAIT_S
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture()
def dummy(tmp_path):
    marker = f"gpu_pause_test_{uuid.uuid4().hex}"
    proc = subprocess.Popen([sys.executable, "-c", "import time\nwhile True: time.sleep(0.05)", marker], stderr=subprocess.PIPE)
    env = _safe_env(tmp_path, GPU_PAUSE_PATTERN=marker)
    yield proc, env, tmp_path / "pauses.log"
    if proc.poll() is None:
        os.kill(proc.pid, 18)  # SIGCONT, then kill
        proc.kill()


def _safe_env(tmp_path, **overrides):
    """Every discovery route of the script pointed at the test only: the pattern, an empty pid-file folder, an executable pattern that
    matches nothing, and a fake nvidia-smi that lists no GPU process (real jobs may be running on this machine)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    fake = bin_dir / "nvidia-smi"
    fake.write_text('#!/bin/bash\nprintf "%s" "${FAKE_GPU_PIDS:-}"\n')
    fake.chmod(0o755)
    (tmp_path / "pids").mkdir(exist_ok=True)
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", GPU_PAUSE_LOG=str(tmp_path / "pauses.log"),
               SVG_SHARED_DIR=str(tmp_path / "shared"),          # the shared pause log: never the machine's real one
               GPU_PAUSE_PIDDIR=str(tmp_path / "pids"), GPU_PAUSE_EXE=f"no_such_exe_{uuid.uuid4().hex}",
               GPU_PAUSE_PATTERN=f"no_such_job_{uuid.uuid4().hex}", FAKE_GPU_PIDS="")
    env.update(overrides)
    return env


def _run(env, *args):
    return subprocess.run(["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True)


def test_pause_resume_status_and_log(dummy):
    proc, env, log = dummy
    assert _wait(lambda: _state(proc.pid) in "SR")
    out = _run(env, "status")
    assert out.returncode == 0 and str(proc.pid) in out.stdout
    assert _run(env, "pause").returncode == 0
    assert _wait(lambda: _state(proc.pid) == "T")
    assert _run(env, "resume").returncode == 0
    assert _wait(lambda: _state(proc.pid) in "SR")
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert [r["event"] for r in rows] == ["pause", "resume"] and rows[0]["pids"] == [proc.pid] and rows[0]["time"] <= rows[1]["time"]


def test_stop_interrupts_a_paused_job(dummy):
    proc, env, log = dummy
    assert _wait(lambda: _state(proc.pid) in "SR")
    _run(env, "pause")
    assert _wait(lambda: _state(proc.pid) == "T")
    out = _run(env, "stop")
    assert out.returncode == 0 and "resume" in out.stdout.lower()
    assert _wait(lambda: proc.poll() is not None)
    assert b"KeyboardInterrupt" in proc.stderr.read()
    assert [json.loads(line)["event"] for line in log.read_text().splitlines()] == ["pause", "stop"]


def test_no_jobs_and_bad_command(tmp_path):
    env = _safe_env(tmp_path)
    assert "no GPU job" in _run(env, "status").stdout
    assert _run(env, "frobnicate").returncode != 0


@pytest.fixture()
def anonymous():
    """A Python process whose command line names no job (like NUS's trainer, which renames its process)."""
    proc = subprocess.Popen([sys.executable, "-c", "import time\nwhile True: time.sleep(0.05)"])
    yield proc
    if proc.poll() is None:
        os.kill(proc.pid, 18)
        proc.kill()


def test_a_renamed_job_is_found_by_its_pid_file(tmp_path, anonymous):
    import re
    (tmp_path / "pids").mkdir(exist_ok=True)
    (tmp_path / "pids" / "2026-11-18_c0_job.pid").write_text(f"{anonymous.pid}\n")
    stale = _safe_env(tmp_path)                       # a pid file whose pid now belongs to a program of another executable: ignored
    assert "no GPU job" in _run(stale, "status").stdout
    env = _safe_env(tmp_path, GPU_PAUSE_EXE=re.escape(os.path.realpath(sys.executable)))
    assert str(anonymous.pid) in _run(env, "status").stdout
    _run(env, "pause")
    assert _wait(lambda: _state(anonymous.pid) == "T")
    _run(env, "resume")
    assert _wait(lambda: _state(anonymous.pid) in "SR")


def test_a_gpu_process_of_our_environments_is_found_by_its_executable(tmp_path, anonymous):
    import re
    exe = os.path.realpath(sys.executable)
    env = _safe_env(tmp_path, GPU_PAUSE_EXE=re.escape(exe), FAKE_GPU_PIDS=f"{anonymous.pid}\n")
    assert str(anonymous.pid) in _run(env, "status").stdout
    other = _safe_env(tmp_path, FAKE_GPU_PIDS=f"{anonymous.pid}\n")          # a GPU process of another executable: not ours
    assert "no GPU job" in _run(other, "status").stdout


def test_default_pattern_covers_every_kind_of_job():
    text = SCRIPT.read_text()
    for name in ("nus_selfplay_train", "nus_phase5_reference", "nus_phase5_score", "train_standin", "nus_isaac_clips", "make_s2b_video",
                 "ma_skills/scripts/train", "ma_skills/scripts/eval"):
        assert name in text, name
    assert "nus_jax" in text and "env_isaaclab" in text and "nus_jax_runs" in text


# ------------------------------------------------------------------------------------------------ STE track, task L0.7
def _lines(path: Path) -> list[str]:
    return path.read_text().splitlines()


def test_every_event_line_also_goes_to_the_shared_log(dummy, tmp_path):
    """One line per event, the SAME text in the legacy log and in the shared log (the reader de-duplicates on it)."""
    proc, env, log = dummy
    shared_log = tmp_path / "shared" / "pauses.log"
    assert _wait(lambda: _state(proc.pid) in "SR")
    assert _run(env, "status").returncode == 0 and not shared_log.exists() and not log.exists()     # status logs nothing
    for command in ("pause", "resume", "pause", "stop"):
        assert _run(env, command).returncode == 0
    assert _wait(lambda: proc.poll() is not None)
    assert _lines(shared_log) == _lines(log) and len(_lines(log)) == 4
    rows = [json.loads(line) for line in _lines(shared_log)]
    assert [r["event"] for r in rows] == ["pause", "resume", "pause", "stop"] and all(r["pids"] == [proc.pid] for r in rows)
    assert [r["time"] for r in rows] == sorted(r["time"] for r in rows)


def test_one_line_when_the_legacy_log_is_the_shared_log(tmp_path):
    shared_log = tmp_path / "shared" / "pauses.log"
    env = _safe_env(tmp_path, GPU_PAUSE_LOG=str(tmp_path / "shared" / "." / "pauses.log"))       # the same file, spelled differently
    assert _run(env, "pause").returncode == 0
    assert len(_lines(shared_log)) == 1 and json.loads(_lines(shared_log)[0])["pids"] == []


def _copy_of_the_script(worktree: Path) -> Path:
    copy = worktree / "svg_training" / "scripts" / "gpu_pause.sh"
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_text(SCRIPT.read_text())
    return copy


def test_default_logs_from_the_main_clone_and_from_a_worktree(tmp_path):
    """No variable set: the legacy log stays inside the copy's own worktree (as before), the shared log is
    ``<main clone>/svg_training/runs/shared/pauses.log`` from both, and it is the folder ste/shared.py computes."""
    from _ste_tools import make_repo
    from svg_training.ste import shared
    main, other = make_repo(tmp_path)
    env = _safe_env(tmp_path)
    del env["GPU_PAUSE_LOG"], env["SVG_SHARED_DIR"]
    legacy = Path("svg_training", "runs", "nus_port", "phase5", "pauses.log")
    shared_log = main / "svg_training" / "runs" / "shared" / "pauses.log"
    for count, worktree in enumerate((other, main), start=1):
        out = subprocess.run(["bash", str(_copy_of_the_script(worktree)), "pause"], env=env, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        assert len(_lines(worktree / legacy)) == 1 and len(_lines(shared_log)) == count
        assert _lines(worktree / legacy)[0] == _lines(shared_log)[-1]
    saved = os.environ.pop("SVG_SHARED_DIR")
    try:
        assert shared.shared_dir(create=False, start=other / "svg_training" / "scripts") / "pauses.log" == shared_log
        assert shared.shared_dir(create=False, start=main / "svg_training" / "scripts") / "pauses.log" == shared_log
    finally:
        os.environ["SVG_SHARED_DIR"] = saved


def test_a_pause_still_works_where_the_shared_folder_cannot_be_found(tmp_path):
    """Outside a git repository and without SVG_SHARED_DIR: the owner's pause must not fail; the legacy line is written
    and a warning says the shared log was not."""
    env = _safe_env(tmp_path, GIT_CEILING_DIRECTORIES=str(tmp_path))
    del env["GPU_PAUSE_LOG"], env["SVG_SHARED_DIR"]
    lone = tmp_path / "not_a_repo"
    out = subprocess.run(["bash", str(_copy_of_the_script(lone)), "pause"], env=env, capture_output=True, text=True)
    assert out.returncode == 0 and "paused 0 job(s)" in out.stdout
    assert "shared pause log" in out.stderr
    assert len(_lines(lone / "svg_training" / "runs" / "nus_port" / "phase5" / "pauses.log")) == 1


def _python_named(path: Path, *args: str) -> subprocess.Popen:
    """A Python process whose command line is ``python <path> <args>`` and that only sleeps."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("import time\nwhile True: time.sleep(0.05)\n")
    return subprocess.Popen([sys.executable, str(path), *args])


def test_default_pattern_finds_the_tracks_jobs_but_not_its_tooling(tmp_path):
    """``status`` only (it sends no signal): with the DEFAULT pattern real jobs of this machine may be listed too."""
    tag = uuid.uuid4().hex
    job = _python_named(tmp_path / tag / "scripts" / "ste_screen_sweep.py", "--run-dir", "runs/x")
    tools = [_python_named(tmp_path / tag / "scripts" / "ste_job.py", "wait", "ste_screen_sweep"),              # the waiter
             _python_named(tmp_path / tag / "scripts" / "ste_job.py", "_run", "runs/scripts/ste_screen_sweep.py"),   # the wrapper
             _python_named(tmp_path / tag / "scripts" / "not_ste_tool.py", "x")]
    try:
        env = _safe_env(tmp_path)
        del env["GPU_PAUSE_PATTERN"]
        assert _wait(lambda: all(_state(p.pid) in "SR" for p in [job, *tools]))
        out = _run(env, "status")
        assert out.returncode == 0
        listed = {int(line.split()[0]) for line in out.stdout.splitlines() if line.split() and line.split()[0].isdigit()}
        assert job.pid in listed
        assert not listed & {p.pid for p in tools}
        assert not (tmp_path / "shared").exists() and not (tmp_path / "pauses.log").exists()
    finally:
        for proc in [job, *tools]:
            proc.kill()
            proc.wait()


def test_the_exclusion_can_be_changed_or_switched_off(tmp_path):
    marker = f"gpu_pause_test_{uuid.uuid4().hex}"
    proc = _python_named(tmp_path / "scripts" / "ste_job.py", marker)
    try:
        assert _wait(lambda: _state(proc.pid) in "SR")
        assert "no GPU job" in _run(_safe_env(tmp_path, GPU_PAUSE_PATTERN=marker), "status").stdout
        assert str(proc.pid) in _run(_safe_env(tmp_path, GPU_PAUSE_PATTERN=marker, GPU_PAUSE_EXCLUDE=""), "status").stdout
        assert "no GPU job" in _run(_safe_env(tmp_path, GPU_PAUSE_PATTERN=marker, GPU_PAUSE_EXCLUDE=marker[-12:]), "status").stdout
    finally:
        proc.kill()
        proc.wait()


def test_script_syntax_and_the_documented_names():
    assert subprocess.run(["bash", "-n", str(SCRIPT)]).returncode == 0
    text = SCRIPT.read_text()
    for name in ("SVG_SHARED_DIR", "GPU_PAUSE_EXCLUDE", "runs/shared/pauses.log", "runs/nus_port/phase5/pauses.log", r"scripts/ste_"):
        assert name in text, name


# ------------------------------------------------------------------------------------------------ STE track, L07-C1b
def test_a_pause_is_the_owners_unless_the_session_tags_it(dummy):
    """L07-C1b: the "by" field is the user name, as before, for a bare ``gpu_pause.sh pause`` (what the owner types).
    The lead tags its own pause with GPU_PAUSE_BY=lead; the CLI is unchanged."""
    proc, env, log = dummy
    assert _wait(lambda: _state(proc.pid) in "SR")
    owner_env = dict(env)
    owner_env.pop("GPU_PAUSE_BY", None)
    assert _run(owner_env, "pause").returncode == 0
    assert _run(owner_env, "resume").returncode == 0
    assert _run(dict(env, GPU_PAUSE_BY="lead"), "pause").returncode == 0
    assert _run(dict(env, GPU_PAUSE_BY="lead"), "resume").returncode == 0
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert [row["by"] for row in rows] == [os.environ.get("USER", "unknown")] * 2 + ["lead"] * 2
    assert all(row["pids"] == [proc.pid] for row in rows)


@pytest.mark.parametrize("tag", ['le"ad', "lead x", "lead\\", ""])
def test_a_tag_that_would_break_the_line_is_refused_before_any_signal(dummy, tag):
    """The tag goes into a JSON line unescaped, so only letters, digits, '.', '_' and '-' are accepted; anything else
    is refused (exit 2) before a process is signalled or a line written. An empty GPU_PAUSE_BY means the default."""
    proc, env, log = dummy
    assert _wait(lambda: _state(proc.pid) in "SR")
    out = _run(dict(env, GPU_PAUSE_BY=tag), "pause")
    if tag == "":
        assert out.returncode == 0 and json.loads(log.read_text())["by"] == os.environ.get("USER", "unknown")
        _run(env, "resume")
        return
    assert out.returncode == 2 and "GPU_PAUSE_BY" in out.stderr
    assert _state(proc.pid) in "SR" and not log.exists()
