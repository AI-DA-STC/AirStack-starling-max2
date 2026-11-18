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
    env = dict(os.environ, GPU_PAUSE_PATTERN=marker, GPU_PAUSE_LOG=str(tmp_path / "pauses.log"))
    yield proc, env, tmp_path / "pauses.log"
    if proc.poll() is None:
        os.kill(proc.pid, 18)  # SIGCONT, then kill
        proc.kill()


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
    env = dict(os.environ, GPU_PAUSE_PATTERN=f"no_such_job_{uuid.uuid4().hex}", GPU_PAUSE_LOG=str(tmp_path / "pauses.log"))
    assert "no GPU job" in _run(env, "status").stdout
    assert _run(env, "frobnicate").returncode != 0
