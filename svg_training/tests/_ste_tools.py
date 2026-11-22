"""Helpers of the STE track's process-tooling tests (task L0.7): a throw-away git repository with one extra worktree,
polling instead of fixed sleeps, and process clean-up that also runs when a test fails. Linux only."""
import os
import signal
import subprocess
import time
from pathlib import Path

from _proc import child_env, child_python
from svg_training.ste.config import TASK_IDS

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
SCRIPTS = ROOT / "scripts"
WAIT_S = 60.0                      # generous: the suite may share the machine with other work
POLL_S = 0.02
LEGACY_REL = Path("svg_training", "runs", "nus_port", "phase5", "pauses.log")


def wait_for(predicate, timeout_s: float = WAIT_S, what: str = "the condition") -> None:
    """Poll until ``predicate()`` is true; fail with ``what`` after ``timeout_s`` seconds."""
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(POLL_S)
    raise AssertionError(f"timed out after {timeout_s:.0f} s waiting for {what}")


def proc_state(pid: int) -> str | None:
    """The one-letter state of a process (R, S, T = stopped, Z = zombie), or None when it is gone."""
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (FileNotFoundError, ProcessLookupError):
        return None


def gone(pid: int) -> bool:
    return proc_state(pid) in (None, "Z")


def kill_group(pid: int) -> None:
    """SIGCONT then SIGKILL the whole process group of ``pid`` (a detached job is its own group); never raises, and
    never touches the test process itself, its parent or its own group."""
    if pid in (os.getpid(), os.getppid(), os.getpgrp()):
        return
    for sig in (signal.SIGCONT, signal.SIGKILL):
        for send in (os.killpg, os.kill):
            try:
                send(pid, sig)
            except (ProcessLookupError, PermissionError):
                pass


def reap(proc: subprocess.Popen) -> None:
    """Kill a child the test started, if it still runs, and collect it."""
    if proc.poll() is None:
        for sig in (signal.SIGCONT, signal.SIGKILL):
            try:
                os.kill(proc.pid, sig)
            except ProcessLookupError:
                pass
    try:
        proc.wait(timeout=WAIT_S)
    except subprocess.TimeoutExpired:
        pass


def tool_env(shared: Path, **extra: str) -> dict:
    """The environment of a child process of these tests: the package on PYTHONPATH, the shared folder under the
    test's own temporary folder, and no legacy pause log read from the machine's real worktrees."""
    env = child_env(str(SOURCE))
    env.update(SVG_SHARED_DIR=str(shared), SVG_PAUSE_LEGACY_LOGS="", PYTHONUNBUFFERED="1")
    env.update(extra)
    return env


def run_py(args: list, env: dict, timeout_s: float = WAIT_S, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run([child_python(), *map(str, args)], env=env, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout_s)


def start_py(args: list, env: dict, log: Path | None = None, cwd: Path = ROOT) -> subprocess.Popen:
    """Start a child Python in its own session (so ``kill_group`` reaches everything it starts)."""
    out = open(log, "ab") if log is not None else subprocess.DEVNULL
    try:
        return subprocess.Popen([child_python(), *map(str, args)], env=env, cwd=cwd, stdin=subprocess.DEVNULL,
                                stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    finally:
        if log is not None:
            out.close()


def pause_script(command: str, tmp_path: Path, shared: Path, pattern: str, legacy: Path | None = None) -> None:
    """Run the real ``scripts/gpu_pause.sh`` so that it can only find processes whose command line holds ``pattern``:
    an empty pid-file folder, an executable pattern that matches nothing, a fake nvidia-smi that lists no GPU process
    (real jobs may be running on this machine). ``shared``: the shared folder it logs to; ``legacy``: its legacy log."""
    bin_dir = tmp_path / "pause_bin"
    bin_dir.mkdir(exist_ok=True)
    fake = bin_dir / "nvidia-smi"
    fake.write_text("#!/bin/bash\n")
    fake.chmod(0o755)
    (tmp_path / "pause_pids").mkdir(exist_ok=True)
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", GPU_PAUSE_PATTERN=pattern,
               GPU_PAUSE_EXE="no_such_executable_anywhere", GPU_PAUSE_PIDDIR=str(tmp_path / "pause_pids"),
               GPU_PAUSE_LOG=str(legacy if legacy is not None else tmp_path / "legacy_pauses.log"),
               SVG_SHARED_DIR=str(shared))
    done = subprocess.run(["bash", str(SCRIPTS / "gpu_pause.sh"), command], env=env, capture_output=True, text=True,
                          timeout=WAIT_S)
    assert done.returncode == 0, done.stderr


def settings(tmp_path: Path, phase_cap: float, **caps: float) -> Path:
    """A test-only settings file with phase L0 in work and OPEN (the committed file's L0 is closed since G0, 22 Nov
    2026): the given phase cap, the given task caps (L0_11=3.0 means "L0.11" = 3.0)."""
    named = {name.replace("_", "."): cap for name, cap in caps.items()}
    lines = ["[track]", "plan_version = 2", 'phase = "L0"', "[budget]", "closed = false", f"phase_cap_gpu_h = {phase_cap!r}",
             "[budget.task_cap_gpu_h]", *(f'"{task}" = {named.get(task, 0.0)!r}' for task in TASK_IDS["L0"])]
    path = tmp_path / "ste_learning.toml"
    path.write_text("\n".join(lines) + "\n")
    return path


def git(folder: Path, *args: str) -> str:
    done = subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", "-C", str(folder),
                           *args], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def make_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A git repository ``main`` with one commit and a second worktree ``other``; both hold ``svg_training/``."""
    main, other = tmp_path / "main", tmp_path / "other"
    (main / "svg_training").mkdir(parents=True)
    git(main, "init", "-q", "-b", "main")
    (main / "svg_training" / "keep.txt").write_text("x\n")
    git(main, "add", "svg_training/keep.txt")
    git(main, "commit", "-q", "-m", "first")
    git(main, "worktree", "add", "-q", str(other), "-b", "other")
    return main, other
