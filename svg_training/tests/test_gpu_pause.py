"""scripts/gpu_pause.sh (owner, 18 Nov 2026): pause = SIGSTOP, resume = SIGCONT, stop = SIGINT (then SIGCONT, so a paused job receives
it), status lists the jobs; every pause, resume and stop is appended to the pause log. The test runs a dummy Python process whose command
line holds a unique marker and points the script at that marker and a private log, so no real job can be touched."""
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
