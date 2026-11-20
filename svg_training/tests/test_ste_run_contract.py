"""STE learning track, task L0.7: the trainer contract (ste/run_contract.py), proved on scripts/ste_dummy_job.py.

Every GPU job of the track must: resume from its checkpoint when the SAME command is run again; turn SIGINT or SIGTERM
into a checkpoint and the "interrupted" exit code; stop at its cap, counted in EFFECTIVE time (wall clock less the
owner's pauses), with the "cap" exit code; never let a NaN or an infinity overwrite the last good checkpoint, and say
so with its own exit code; refuse to start a second copy in the same run folder. The dummy job counts steps (step i
adds i to a total), so a lost or repeated step shows in the total."""
import json
import math
import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

from _ste_tools import (SCRIPTS, SOURCE, WAIT_S, kill_group, pause_script, proc_state, reap, run_py, start_py,
                        tool_env, wait_for)
from _proc import child_env, child_python
from svg_training.ste import run_contract as rc
from svg_training.ste import pauses, shared

DUMMY = SCRIPTS / "ste_dummy_job.py"
T0 = 2_000_000.0


def test_exit_codes_are_distinct_and_reuse_the_repositorys():
    """0 done; 2 refused, 3 cap, 4 interrupted as scripts/nus_selfplay_train.py (EXIT_REFUSED, EXIT_ABORTED,
    EXIT_STOPPED) and CODING_PRACTICES section 8; 5 non-finite is new (see the module docstring for why)."""
    codes = (rc.EXIT_DONE, rc.EXIT_REFUSED, rc.EXIT_CAP, rc.EXIT_INTERRUPTED, rc.EXIT_NONFINITE)
    assert codes == (0, 2, 3, 4, 5) and len(set(codes)) == len(codes)
    assert rc.EXIT_FOR_STOP == {rc.STOP_INTERRUPTED: rc.EXIT_INTERRUPTED, rc.STOP_CAP: rc.EXIT_CAP}
    assert [rc.EXIT_NAMES[code] for code in codes] == ["DONE", "REFUSED", "CAP", "INTERRUPTED", "NONFINITE"]
    text = (SCRIPTS / "nus_selfplay_train.py").read_text()
    assert "EXIT_REFUSED, EXIT_ABORTED, EXIT_STOPPED = 2, 2 + 1, 2 + 2" in text      # the codes reused, still there


def test_a_failed_control_has_its_own_exit_code_6():
    """LEAD CALL 21 Nov 2026 (L0.11): a control with a known answer that fails ends the run with its own code, a terminal
    state the automation never retries; every other code is unchanged."""
    assert rc.EXIT_CONTROL_FAILED == 6 and rc.EXIT_NAMES[rc.EXIT_CONTROL_FAILED] == "CONTROL_FAILED"
    assert len(set(rc.EXIT_NAMES)) == len(rc.EXIT_NAMES) == 6
    assert [rc.EXIT_DONE, rc.EXIT_REFUSED, rc.EXIT_CAP, rc.EXIT_INTERRUPTED, rc.EXIT_NONFINITE] == [0, 2, 3, 4, 5]


# ================================================================================================ the guard, in process
class Clock:
    def __init__(self, now: float = T0):
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture()
def quiet(tmp_path, monkeypatch):
    """A private shared folder with no pause in it."""
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    return tmp_path / "shared" / "pauses.log"


def pause_line(log: Path, event: str, time_s: float, pids: list | None = None) -> None:
    """One gpu_pause.sh line. ``pids``: the processes it stopped; default this test process, where the guard runs (a
    pause counts only for the jobs it stopped, L07-C1)."""
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as stream:
        stream.write(json.dumps({"event": event, "time": time_s, "pids": [os.getpid()] if pids is None else pids,
                                 "by": "tester"}) + "\n")


def test_save_and_load_latest(tmp_path, quiet):
    run = tmp_path / "run"
    with rc.RunGuard(run, cap_s=math.inf) as guard:
        assert guard.load_latest() is None
        guard.save(3, {"total": 6.0})
        guard.save(4, {"total": 10.0})
        assert guard.load_latest() == rc.Checkpoint(step=4, state={"total": 10.0}, effective_s=guard.load_latest().effective_s)
    assert sorted(p.name for p in run.iterdir()) == sorted([rc.CHECKPOINT_NAME, rc.LOCK_NAME, rc.PROGRESS_NAME])  # no temporary file
    with rc.RunGuard(run, cap_s=math.inf) as again:
        assert again.load_latest().step == 4 and again.load_latest().state == {"total": 10.0}


def test_every_save_also_writes_the_progress_the_waiter_reads(tmp_path, quiet):
    """L07-I4: the checkpoint may be a PyTorch file the standard-library waiter cannot read, so each save also writes
    ``progress.json`` (JSON): the step, the run folder's effective seconds and when it was saved."""
    clock = Clock()
    run = tmp_path / "run"
    with rc.RunGuard(run, cap_s=math.inf, clock=clock) as guard:
        clock.now = T0 + 12.5
        guard.save(3, {"total": 6.0})
    assert json.loads((run / rc.PROGRESS_NAME).read_text()) == {"step": 3, "effective_s": 12.5, "saved": T0 + 12.5}
    with rc.RunGuard(run, cap_s=math.inf, clock=clock) as again:              # a relaunch carries the time on
        again.load_latest()
        clock.now = T0 + 20.0
        again.save(4, {"total": 10.0})
    assert json.loads((run / rc.PROGRESS_NAME).read_text()) == {"step": 4, "effective_s": 20.0, "saved": T0 + 20.0}


def test_the_progress_note_never_breaks_a_save(tmp_path, quiet, monkeypatch, capsys):
    """L07-I4: ``progress.json`` is a note for the waiter. A step JSON cannot hold (a PyTorch or NumPy integer, here a
    Fraction) is written as a plain int; a step with no int value is left out; a failed note write (a full disk) is
    said on stderr. None of them makes the save fail, and the checkpoint loads."""
    import fractions
    import pickle

    def dump(obj, path):
        Path(path).write_bytes(pickle.dumps(obj))

    def load(path):
        return pickle.loads(Path(path).read_bytes())

    run = tmp_path / "run"
    with rc.RunGuard(run, cap_s=math.inf, dump=dump, load=load) as guard:
        guard.save(fractions.Fraction(6, 2), {"total": 6.0})
        assert json.loads((run / rc.PROGRESS_NAME).read_text())["step"] == 3
        odd = object()
        guard.save(odd, {"total": 7.0})
        assert json.loads((run / rc.PROGRESS_NAME).read_text())["step"] is None
        real = rc.atomic.write_text

        def full(path, text):
            if Path(path).name == rc.PROGRESS_NAME:
                raise OSError(28, "No space left on device (injected)")
            return real(path, text)

        monkeypatch.setattr(rc.atomic, "write_text", full)
        guard.save(4, {"total": 10.0})
        assert guard.load_latest().state == {"total": 10.0}
    assert "progress.json" in capsys.readouterr().err


def test_a_crash_while_saving_keeps_the_last_checkpoint(tmp_path, quiet, monkeypatch):
    run = tmp_path / "run"
    with rc.RunGuard(run, cap_s=math.inf) as guard:
        guard.save(1, {"total": 1.0})

        def half_written(obj, path):
            Path(path).write_text('{"step": 2, "sta')
            raise OSError("power cut")

        guard.dump = half_written
        with pytest.raises(OSError, match="power cut"):
            guard.save(2, {"total": 3.0})
        assert guard.load_latest().step == 1
    (run / f"{rc.CHECKPOINT_NAME}.tmp.99999").write_text("left by a killed process")           # never read
    with rc.RunGuard(run, cap_s=math.inf) as again:
        assert again.load_latest().step == 1 and again.load_latest().state == {"total": 1.0}


@pytest.mark.parametrize("bad_state, where", [
    ({"total": math.nan}, "state.total"), ({"total": math.inf}, "state.total"), ({"total": -math.inf}, "state.total"),
    ({"total": 21.0, "more": {"deep": [1.0, math.nan]}}, r"state.more.deep\[1\]"),
])
def test_a_non_finite_value_never_overwrites_the_last_good_checkpoint(tmp_path, quiet, bad_state, where):
    with rc.RunGuard(tmp_path / "run", cap_s=math.inf) as guard:
        guard.save(5, {"total": 15.0})
        guard.check_finite(loss=0.25, grads=[1.0, 2.0], nested={"a": (3, 4.5)}, note="text is ignored", flag=True)
        with pytest.raises(rc.NonFiniteError, match=where):
            guard.save(6, bad_state)                                # the state itself is checked at every save
        assert guard.load_latest().step == 5 and guard.load_latest().state == {"total": 15.0}
    assert json.loads((tmp_path / "run" / rc.CHECKPOINT_NAME).read_text())["state"] == {"total": 15.0}


def test_after_a_non_finite_value_the_guard_saves_nothing_more(tmp_path, quiet):
    """The trainer's networks may already hold the NaN when a loss shows it: a later save of a state that looks fine
    must not replace the last good checkpoint either."""
    with rc.RunGuard(tmp_path / "run", cap_s=math.inf) as guard:
        guard.save(5, {"total": 15.0})
        with pytest.raises(rc.NonFiniteError, match="loss"):
            guard.check_finite(loss=math.nan)
        assert guard.nonfinite
        with pytest.raises(rc.NonFiniteError, match="last good checkpoint"):
            guard.save(6, {"total": 21.0})
        assert guard.load_latest().step == 5


def test_other_savers_and_loaders_fit(tmp_path, quiet):
    """A trainer hands in its own saver and loader (``torch.save`` and ``torch.load`` have this shape)."""
    import pickle

    def dump(obj, path):
        Path(path).write_bytes(pickle.dumps(obj))

    def load(path):
        return pickle.loads(Path(path).read_bytes())

    with rc.RunGuard(tmp_path / "run", cap_s=math.inf, dump=dump, load=load) as guard:
        guard.save(2, {"weights": (1.5, 2.5), "names": {"a", "b"}})
        assert guard.load_latest().state == {"weights": (1.5, 2.5), "names": {"a", "b"}}


def test_cap_is_counted_in_effective_time(tmp_path, quiet):
    """Wall clock less the paused intervals of the pause log (made-up clock, made-up log)."""
    clock = Clock()
    with rc.RunGuard(tmp_path / "run", cap_s=100.0, clock=clock) as guard:
        assert guard.effective_s() == 0.0 and guard.stop_reason() is None
        clock.now = T0 + 60
        assert guard.effective_s() == 60.0 and not guard.cap_reached()
        pause_line(quiet, "pause", T0 + 60)
        clock.now = T0 + 5000                                       # the owner played for 82 minutes
        assert guard.effective_s() == 60.0 and guard.stop_reason() is None
        pause_line(quiet, "resume", T0 + 5000)
        clock.now = T0 + 5039
        assert guard.effective_s() == 99.0 and guard.stop_reason() is None
        clock.now = T0 + 5040
        assert guard.effective_s() == 100.0 and guard.cap_reached() and guard.stop_reason() == rc.STOP_CAP


def test_without_the_pause_in_the_log_the_same_clock_hits_the_cap(tmp_path, quiet):
    clock = Clock()
    with rc.RunGuard(tmp_path / "run", cap_s=100.0, clock=clock) as guard:
        clock.now = T0 + 5000
        assert guard.effective_s() == 5000.0 and guard.stop_reason() == rc.STOP_CAP


@pytest.mark.parametrize("pids", [[], [os.getpid() + 1]], ids=["stopped_nothing", "stopped_another_job"])
def test_qc_reproduction_a_pause_that_did_not_stop_the_job_does_not_hold_its_cap(tmp_path, quiet, pids, monkeypatch):
    """L07-C1, the QC scratch reproduction: a pause opened 60 s before the guard started and never resumed, that did not
    stop this process. Before the fix: effective 0.0 s and no cap after 1.5 s of a 1 s cap. The job runs, so its clock
    must run too."""
    monkeypatch.setattr(pauses, "boot_time_s", lambda: 0.0)                     # the made-up clock is after the boot
    pause_line(quiet, "pause", T0 - 60, pids)
    clock = Clock()
    with rc.RunGuard(tmp_path / "run", cap_s=1.0, clock=clock) as guard:
        clock.now = T0 + 1.5
        assert guard.effective_s() == 1.5 and guard.cap_reached() and guard.stop_reason() == rc.STOP_CAP


def test_a_pause_that_stopped_the_job_still_holds_its_cap(tmp_path, quiet, monkeypatch):
    """L07-C1, the other side: the same open pause, listing this process, still stops the clock."""
    monkeypatch.setattr(pauses, "boot_time_s", lambda: 0.0)
    pause_line(quiet, "pause", T0 - 60, [os.getpid() + 1, os.getpid()])
    clock = Clock()
    with rc.RunGuard(tmp_path / "run", cap_s=1.0, clock=clock) as guard:
        clock.now = T0 + 1.5
        assert guard.effective_s() == 0.0 and not guard.cap_reached()


def test_effective_time_is_carried_through_the_checkpoint(tmp_path, quiet):
    """A resumed run continues the count: the cap is one cap for the run folder, not one per launch."""
    clock = Clock()
    with rc.RunGuard(tmp_path / "run", cap_s=100.0, clock=clock) as guard:
        clock.now = T0 + 70
        guard.save(7, {"total": 28.0})
    clock.now = T0 + 900                                            # down for a while: not counted
    with rc.RunGuard(tmp_path / "run", cap_s=100.0, clock=clock) as again:
        assert again.effective_s() == 0.0                           # nothing loaded yet: a fresh run
        assert again.load_latest().effective_s == 70.0
        assert again.effective_s() == 70.0 and again.stop_reason() is None
        clock.now = T0 + 930
        assert again.effective_s() == 100.0 and again.stop_reason() == rc.STOP_CAP


def test_signals_ask_for_a_stop_and_the_old_handlers_come_back(tmp_path, quiet):
    before = (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM))
    for number in (signal.SIGINT, signal.SIGTERM):
        with rc.RunGuard(tmp_path / "run", cap_s=math.inf) as guard:
            assert guard.stop_reason() is None and not guard.stop_requested
            os.kill(os.getpid(), number)
            wait_for(lambda: guard.stop_requested, what="the signal")
            assert guard.stop_reason() == rc.STOP_INTERRUPTED and guard.stop_signal == number
        assert (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)) == before


def test_interrupted_wins_over_cap(tmp_path, quiet):
    clock = Clock()
    with rc.RunGuard(tmp_path / "run", cap_s=1.0, clock=clock) as guard:
        clock.now = T0 + 50
        assert guard.stop_reason() == rc.STOP_CAP
        os.kill(os.getpid(), signal.SIGINT)
        wait_for(lambda: guard.stop_requested, what="the signal")
        assert guard.stop_reason() == rc.STOP_INTERRUPTED


def test_a_second_guard_on_the_same_run_folder_is_refused(tmp_path, quiet):
    with rc.RunGuard(tmp_path / "run", cap_s=math.inf):
        with pytest.raises(rc.RunBusyError, match="run"):
            with rc.RunGuard(tmp_path / "run", cap_s=math.inf):
                pass
    with rc.RunGuard(tmp_path / "run", cap_s=math.inf):             # free again once the first has left
        pass


def test_cap_must_be_a_positive_number(tmp_path, quiet):
    for bad in (0.0, -1.0, math.nan):
        with pytest.raises(ValueError, match="cap_s"):
            rc.RunGuard(tmp_path / "run", cap_s=bad)


def test_importing_loads_no_pytorch():
    code = ("import sys\nimport svg_training.ste.run_contract\n"
            "assert 'torch' not in sys.modules and 'numpy' not in sys.modules\n")
    done = subprocess.run([child_python(), "-c", code], env=child_env(str(SOURCE)), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


# ================================================================================================ the dummy job, as processes
STEPS, EVERY = 40, 4
TOTAL = STEPS * (STEPS + 1) / 2


class Job:
    """One run folder and the command that is run on it again and again."""

    def __init__(self, tmp_path: Path, steps: int = STEPS, step_s: float = 0.03, cap_s: float = 600.0,
                 every: int = EVERY, extra: tuple = ()):
        self.run = tmp_path / "run_dir"
        self.log = tmp_path / "job.log"
        self.shared = tmp_path / "shared"
        self.env = tool_env(self.shared)
        self.args = [DUMMY, "--run-dir", self.run, "--steps", steps, "--step-s", step_s, "--cap-s", cap_s,
                     "--checkpoint-every", every, *extra]
        self.started: list[subprocess.Popen] = []

    def start(self) -> subprocess.Popen:
        proc = start_py(self.args, self.env, self.log)
        self.started.append(proc)
        return proc

    def finish(self) -> int:
        """Run the command to its end; its exit code."""
        return self.start().wait(timeout=WAIT_S)

    def checkpoint(self) -> dict | None:
        path = self.run / rc.CHECKPOINT_NAME
        return json.loads(path.read_text()) if path.exists() else None

    def step(self) -> int:
        found = self.checkpoint()
        return found["step"] if found else 0

    def result(self) -> dict:
        return json.loads((self.run / "result.json").read_text())

    def log_text(self) -> str:
        return self.log.read_text()

    def clean_up(self) -> None:
        for proc in self.started:
            kill_group(proc.pid)
            reap(proc)


@pytest.fixture()
def job(tmp_path):
    made: list[Job] = []

    def make(**settings) -> Job:
        made.append(Job(tmp_path, **settings))
        return made[-1]

    yield make
    for one in made:
        one.clean_up()


def test_an_undisturbed_run_finishes_with_done(job):
    j = job()
    assert j.finish() == rc.EXIT_DONE, j.log_text()
    assert j.result() == {"steps": STEPS, "total": TOTAL} and j.step() == STEPS
    assert "fresh start" in j.log_text()


def test_i_the_same_command_run_again_resumes_from_the_checkpoint_and_finishes(job):
    """(i) Stopped part-way (SIGTERM here), then the same command: it carries on, repeats nothing, and finishes. Run a
    third time, it has nothing left to do."""
    j = job()
    first = j.start()
    wait_for(lambda: j.step() >= EVERY, what="the first checkpoint")
    first.send_signal(signal.SIGTERM)
    assert first.wait(timeout=WAIT_S) == rc.EXIT_INTERRUPTED, j.log_text()
    stopped_at = j.step()
    assert 0 < stopped_at < STEPS and not (j.run / "result.json").exists()
    assert j.finish() == rc.EXIT_DONE, j.log_text()
    assert f"resumed from step {stopped_at}" in j.log_text()
    assert j.result() == {"steps": STEPS, "total": TOTAL}
    steps_done = [int(line.split()[2]) for line in j.log_text().splitlines() if line.startswith("[dummy] step ")]
    assert steps_done == list(range(1, STEPS + 1))                  # every step once, none twice
    assert j.finish() == rc.EXIT_DONE and f"resumed from step {STEPS}" in j.log_text()
    assert j.result() == {"steps": STEPS, "total": TOTAL}


def test_ii_sigint_gives_a_checkpoint_and_the_interrupted_code_then_the_same_command_resumes(job):
    """(ii) ``gpu_pause.sh stop`` and Ctrl-C send SIGINT."""
    j = job()
    first = j.start()
    wait_for(lambda: j.step() >= EVERY, what="the first checkpoint")
    before = j.step()
    first.send_signal(signal.SIGINT)
    assert first.wait(timeout=WAIT_S) == rc.EXIT_INTERRUPTED == 4, j.log_text()
    stopped_at = j.step()
    assert before <= stopped_at < STEPS
    assert f"stopped (interrupted) at step {stopped_at}" in j.log_text() and "Traceback" not in j.log_text()
    assert j.checkpoint()["state"]["total"] == stopped_at * (stopped_at + 1) / 2       # saved at the stop, not earlier
    assert j.finish() == rc.EXIT_DONE, j.log_text()
    assert f"resumed from step {stopped_at}" in j.log_text() and j.result() == {"steps": STEPS, "total": TOTAL}


def test_iii_sigkill_then_the_same_command_resumes_from_the_last_checkpoint(job):
    """(iii) SIGKILL stands in for a power cut: no handler runs, nothing is saved at the kill. The steps after the last
    checkpoint are done again; the total is still exact because it travels in the checkpoint."""
    j = job()
    first = j.start()
    wait_for(lambda: j.step() >= 2 * EVERY, what="the second checkpoint")
    first.kill()
    assert first.wait(timeout=WAIT_S) == -signal.SIGKILL
    survived = j.step()
    assert 2 * EVERY <= survived < STEPS and survived % EVERY == 0
    assert "stopped" not in j.log_text() and not (j.run / "result.json").exists()
    assert j.finish() == rc.EXIT_DONE, j.log_text()
    assert f"resumed from step {survived}" in j.log_text() and j.result() == {"steps": STEPS, "total": TOTAL}


def test_iv_an_injected_nan_gives_the_nan_code_and_keeps_the_last_good_checkpoint(job):
    """(iv) The NaN arrives at step 11; the last checkpoint before it (step 8) stays, finite and loadable. Running the
    same command again hits the NaN again: nothing retries a NaN silently (AUTOMATION section 5)."""
    j = job(extra=("--nan-at-step", 11))
    assert j.finish() == rc.EXIT_NONFINITE == 5, j.log_text()
    kept = j.checkpoint()
    assert kept["step"] == 8 and kept["state"] == {"total": 36.0} and math.isfinite(kept["state"]["total"])
    assert "non-finite" in j.log_text() and not (j.run / "result.json").exists()
    assert j.finish() == rc.EXIT_NONFINITE and j.checkpoint() == kept
    assert j.log_text().count("resumed from step 8") == 1


def test_v_the_cap_gives_the_cap_code_with_a_checkpoint(job):
    """(v) A cap far below the job's length: it stops at the cap with what it had, and the same command stops again at
    once, because the time already used travels in the checkpoint."""
    j = job(steps=100_000, step_s=0.02, cap_s=0.4)
    assert j.finish() == rc.EXIT_CAP == 3, j.log_text()
    kept = j.checkpoint()
    assert 0 < kept["step"] < 100_000 and kept["effective_s"] >= 0.4
    assert kept["state"]["total"] == kept["step"] * (kept["step"] + 1) / 2
    assert f"stopped (cap) at step {kept['step']}" in j.log_text()
    assert j.finish() == rc.EXIT_CAP
    assert j.step() == kept["step"]


PAUSE_CAP_S = 3.0          # ten times the job's own running time (10 steps of 0.03 s), so only a pause can reach it


def paused_run(j: Job, tmp_path: Path, logged: bool) -> int:
    """Start the job, SIGSTOP it part-way, keep it stopped until the wall clock since its start is past the cap, then
    SIGCONT it. ``logged``: stop and continue with the real scripts/gpu_pause.sh (it logs both); otherwise with bare
    signals, so no pause log knows. Returns the job's exit code."""
    pattern = j.run.parent.name                                    # unique: pytest's own folder name for this test
    began = time.time()
    proc = j.start()
    wait_for(lambda: j.step() >= 2, what="the first checkpoint")
    if logged:
        pause_script("pause", tmp_path, j.shared, pattern)
    else:
        os.kill(proc.pid, signal.SIGSTOP)
    wait_for(lambda: proc_state(proc.pid) == "T", what="the job to be stopped")
    held = j.step()
    wait_for(lambda: time.time() - began > PAUSE_CAP_S + 0.5, what="the wall clock to pass the cap")
    assert j.step() == held and proc.poll() is None                # it really stood still
    if logged:
        pause_script("resume", tmp_path, j.shared, pattern)
    else:
        os.kill(proc.pid, signal.SIGCONT)
    return proc.wait(timeout=WAIT_S)


def test_vi_a_logged_pause_does_not_count_against_the_cap(job, tmp_path):
    """(vi) and F-e: SIGSTOP and SIGCONT by ``gpu_pause.sh``. The wall clock passes the cap while the job stands
    still; the job still finishes with "done", because the pause is in the log."""
    j = job(steps=10, step_s=0.03, cap_s=PAUSE_CAP_S, every=2)
    assert paused_run(j, tmp_path, logged=True) == rc.EXIT_DONE, j.log_text()
    assert j.result() == {"steps": 10, "total": 55.0}
    events = [json.loads(line)["event"] for line in (j.shared / "pauses.log").read_text().splitlines()]
    assert events == ["pause", "resume"]
    assert j.checkpoint()["effective_s"] < PAUSE_CAP_S


def test_vi_control_the_same_stop_without_a_log_entry_hits_the_cap(job, tmp_path):
    """The control of (vi): same job, same stop, same timing, but nothing in the pause log. The cap fires."""
    j = job(steps=10, step_s=0.03, cap_s=PAUSE_CAP_S, every=2)
    assert paused_run(j, tmp_path, logged=False) == rc.EXIT_CAP, j.log_text()
    assert 2 <= j.step() < 10 and not (j.run / "result.json").exists()


def test_a_second_copy_in_the_same_run_folder_is_refused(job):
    j = job(steps=100_000)
    first = j.start()
    wait_for(lambda: j.step() >= EVERY, what="the first checkpoint")
    second = run_py(j.args, j.env)
    assert second.returncode == rc.EXIT_REFUSED == 2, second.stderr
    assert "already running" in second.stderr
    assert first.poll() is None                                     # the first copy was not disturbed
    first.send_signal(signal.SIGINT)
    assert first.wait(timeout=WAIT_S) == rc.EXIT_INTERRUPTED


def test_the_dummy_job_refuses_bad_arguments(job, tmp_path):
    j = job()
    bad = run_py([DUMMY, "--run-dir", tmp_path / "x", "--steps", 0, "--step-s", 0.01, "--cap-s", 5, "--checkpoint-every", 1],
                 j.env)
    assert bad.returncode == rc.EXIT_REFUSED and not (tmp_path / "x").exists()
    assert run_py([DUMMY, "--run-dir", tmp_path / "x"], j.env).returncode == rc.EXIT_REFUSED
