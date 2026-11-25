"""STE L5: the automatic post-run 3-D clip hook (``ste/post_run.py``, called by the wrapper of ``scripts/ste_job.py``).

A training job launched with ``--post-clips3d`` that exits 0 and leaves a complete run (``results.json`` with
``complete: true`` and ``agent_final.pt``) starts ``scripts/ste_l5_clips3d.py --run-dir <run>`` as its own recorded job
(``clips3d_<name>``, the run's task and cap, ``<run>/videos3d``), so its GPU-hours land in the ledger. A non-zero exit
or an incomplete run starts nothing; an owner pause, a busy GPU or the task's cap leave ``videos3d/HOOK_STATUS``
"pending" with the retry line; the hook never changes the training job's exit code. The Isaac render is never run:
the clips command and the preflight are stand-ins. CPU only."""
import json
import os
import signal
import sys
import time
from pathlib import Path

import pytest

from _ste_tools import ROOT, SCRIPTS, run_py, settings, tool_env, wait_for
from _proc import child_python
from svg_training.ste import budget, jobs, post_run, shared, state

TOOL = SCRIPTS / "ste_job.py"
REAL_PREFLIGHT = post_run.preflight
TASK = "L0.11"                     # the test settings' open task (the committed caps close phase by phase)
BEAT_S = 0.05


# ================================================================================================ fixtures
@pytest.fixture()
def hook(tmp_path, monkeypatch):
    """The wrapper run in this process (as tests/test_ste_job.py's ``in_process``), a private shared folder, a test
    settings file with an open cap, the preflight and the clips command replaced by stand-ins."""
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")
    saved = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}
    calls = {"preflight": [], "launch": []}

    class Hook:
        caps = settings(tmp_path, phase_cap=5.0, L0_11=1.0)
        preflight_code = 0
        clips_code = 0
        clips_complete = True
        clips_sleep_s = 0.2

        def __init__(self):
            self.tmp = tmp_path

        def run(self, name: str = "train", exit_code: int = 0, complete: bool = True, final: bool = True,
                post: bool = True, gpu_h: float = 0.0, cmd0: str | None = None) -> Path:
            """A recorded training job (this process is its wrapper) whose command exits ``exit_code`` after writing
            the run's files: ``results.json`` (``complete``) and ``agent_final.pt`` (``final``)."""
            run = tmp_path / "runs" / name
            run.mkdir(parents=True)
            me = os.getpid()
            code = ("import json, sys, time\ntime.sleep(0.1)\n"
                    f"open({str(run / 'results.json')!r}, 'w').write(json.dumps({{'complete': {complete!r}}}))\n")
            if final:
                code += f"open({str(run / 'agent_final.pt')!r}, 'wb').write(b'weights')\n"
            code += f"sys.exit({exit_code})\n"
            record = {"task": TASK, "pid": me, "pid_start": jobs._start_ticks(me), "boot_id": state.boot_id(),
                      "cmd": [cmd0 or child_python(), "-c", code], "cwd": str(ROOT), "run_dir": str(run),
                      "log": str(run / "job.log"), "started": time.time(), "expected_min_s": 0.0, "gpu_h": gpu_h,
                      "launch": 1, "child_pid": None, "child_start": None, "exit_code": None, "ended": None}
            state.update(lambda data: data["jobs"].__setitem__(name, dict(record)))
            (run / "job.json").write_text(json.dumps(dict(record, name=name, beat_s=BEAT_S, settings=str(self.caps),
                                                          env={}, shared_dir=str(tmp_path / "shared"),
                                                          post_clips3d=post)))
            return run

        def clips_cmd(self, record: dict, run: Path) -> list[str]:
            """Stand-in for ``ste_l5_clips3d.py``: writes ``clips3d.json`` (complete or not) and exits clips_code."""
            out = run / post_run.CLIPS3D_DIR
            code = (f"import json, sys, time\ntime.sleep({self.clips_sleep_s})\n"
                    f"open({str(out / 'clips3d.json')!r}, 'w').write(json.dumps({{'complete': {self.clips_complete!r}}}))\n"
                    f"sys.exit({self.clips_code})\n")
            return [child_python(), "-c", code]

    made = Hook()

    def fake_preflight(log: Path) -> int:
        calls["preflight"].append(str(log))
        return made.preflight_code

    real_launch = jobs.launch

    def spy_launch(*args, **kwargs):
        calls["launch"].append((args, kwargs))
        return real_launch(*args, **kwargs)

    monkeypatch.setattr(post_run, "preflight", fake_preflight)
    monkeypatch.setattr(post_run, "clips_command", made.clips_cmd)
    monkeypatch.setattr(jobs, "launch", spy_launch)
    made.calls = calls
    yield made
    for job in state.read()["jobs"].values():                 # every clips job this test started has ended
        if job["pid"] != os.getpid():
            wait_for(lambda job=job: not state.job_alive(job), what="the clips job to end")
    for number, handler in saved.items():                     # the wrapper sets its own handlers
        signal.signal(number, handler)


def clips_job(run: Path, name: str = "train") -> dict | None:
    return state.read()["jobs"].get(post_run.clips_name(name))


def wait_clips(name: str = "train") -> jobs.Outcome:
    return jobs.wait(post_run.clips_name(name), poll_s=0.02)


def status_line(run: Path) -> str:
    return (run / post_run.CLIPS3D_DIR / post_run.HOOK_STATUS).read_text().splitlines()[0]


def wrapper_gone(name: str = "train") -> None:
    """This process stood in as the training job's wrapper: mark that wrapper as gone (another process start time), as
    it is once a real wrapper has ended, so a retry by hand sees a finished job."""
    def change(data: dict) -> None:
        data["jobs"][name]["pid_start"] = -1
    state.update(change)


def pause_line(event: str, time_s: float, by: str = "owner") -> None:
    log = shared.pauses_log()
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as stream:
        stream.write(json.dumps({"event": event, "time": time_s, "pids": [], "by": by}) + "\n")


# ================================================================================================ the hook fires
def test_the_hook_fires_on_exit_0_and_a_complete_run_and_records_the_clips_job(hook, capsys):
    run = hook.run(gpu_h=0.3)
    assert jobs.run_wrapper(run) == 0
    assert (run / "exit_code").read_text() == "0\n"                  # the training job's own code, untouched
    assert state.read()["jobs"]["train"]["exit_code"] == 0
    job = clips_job(run)
    assert job is not None, capsys.readouterr().out
    out = run / post_run.CLIPS3D_DIR
    # the clips job: its own recorded job, the run's task and cap, the hand launches' ask, its folder <run>/videos3d
    assert job["task"] == TASK and job["gpu_h"] == post_run.CLIPS3D_GPU_H == 0.1
    assert job["expected_min_s"] == post_run.CLIPS3D_MIN_S == 30.0 and job["run_dir"] == str(out)
    assert job["cwd"] == str(ROOT)
    record = json.loads((out / "job.json").read_text())
    assert record["clips3d_for"] == str(run) and record["post_clips3d"] is False   # it never hooks itself
    assert record["settings"] == str(hook.caps) and record["beat_s"] == BEAT_S
    assert "--clips3d-for" in (out / "cmd.txt").read_text()          # a relaunch by cmd.txt keeps the marker update
    assert status_line(run).startswith("launched:")
    assert hook.calls["preflight"] == [str(out / post_run.PREFLIGHT_LOG)]
    assert "post-run clips3d: launched clips3d_train" in capsys.readouterr().out    # the line in the run's job.log
    outcome = wait_clips()
    assert outcome.exit_code == 0
    assert status_line(run).startswith("done:")                       # updated by the clips job's own wrapper
    assert shared.gpu_hours_log() == hook.tmp / "shared" / "gpu_hours.log"   # runs/shared/gpu_hours.log, here private
    rows = [json.loads(line) for line in shared.gpu_hours_log().read_text().splitlines()]
    mine = [row for row in rows if row["job"] == "clips3d_train"]
    assert mine and all(row["group"] == TASK and row["run_dir"] == str(out) for row in mine)
    assert budget.job_gpu_h(TASK, "clips3d_train", str(out)) > 0     # charged to the run's task
    assert (run / "exit_code").read_text() == "0\n"


def test_the_clips_command_is_the_clip_script_on_the_training_python(tmp_path):
    run = tmp_path / "runs" / "x"
    py = "/opt/envs/env_isaaclab/bin/python3.11"
    cmd = post_run.clips_command({"cmd": [py, "scripts/ste_exploit_l012.py"]}, run)
    assert cmd == [py, str(SCRIPTS / "ste_l5_clips3d.py"), "--run-dir", str(run)]
    wrapped = post_run.clips_command({"cmd": ["env", "X=1", "nice", "/opt/py/bin/python3", "-u", "train.py"]}, run)
    assert wrapped[0] == "/opt/py/bin/python3"                       # the interpreter the launch recorded in its cmd
    other = post_run.clips_command({"cmd": ["bash", "train.sh"]}, run)
    assert other[0] == sys.executable and other[1:] == cmd[1:]       # fallback: the launcher's own interpreter
    assert post_run.clips_name("l5_velocity_guard") == "clips3d_l5_velocity_guard"


# ================================================================================================ it does not fire
@pytest.mark.parametrize("code", [1, 3, 4, 5])
def test_a_non_zero_exit_starts_nothing_and_keeps_its_code(hook, capsys, code):
    run = hook.run(exit_code=code)
    assert jobs.run_wrapper(run) == 0
    assert (run / "exit_code").read_text() == f"{code}\n"
    assert state.read()["jobs"]["train"]["exit_code"] == code
    assert clips_job(run) is None and not hook.calls["launch"] and not hook.calls["preflight"]
    assert not (run / post_run.CLIPS3D_DIR).exists()                  # a failed run folder gains nothing
    assert f"post-run clips3d: not started (the training job exited {code}, not 0)" in capsys.readouterr().out


@pytest.mark.parametrize("complete, final, missing", [(False, True, "results.json"), (True, False, "agent_final.pt")],
                         ids=["results_not_complete", "no_agent_final"])
def test_an_incomplete_run_starts_nothing_and_says_skipped(hook, capsys, complete, final, missing):
    run = hook.run(complete=complete, final=final)
    assert jobs.run_wrapper(run) == 0
    assert (run / "exit_code").read_text() == "0\n"
    assert clips_job(run) is None and not hook.calls["launch"] and not hook.calls["preflight"]
    printed = capsys.readouterr().out
    assert "post-run clips3d: skipped" in printed and missing in printed
    line = status_line(run)
    assert line.startswith("skipped:") and missing in line            # exit 0 but no finished run: said in the marker


def test_without_the_flag_the_wrapper_is_unchanged(hook, capsys):
    run = hook.run(post=False)
    assert jobs.run_wrapper(run) == 0
    assert (run / "exit_code").read_text() == "0\n"
    assert clips_job(run) is None and not hook.calls["launch"] and not hook.calls["preflight"]
    assert "clips3d" not in capsys.readouterr().out and not (run / post_run.CLIPS3D_DIR).exists()


def test_clips_already_complete_are_not_drawn_again(hook):
    run = hook.run()
    out = run / post_run.CLIPS3D_DIR
    out.mkdir()
    (out / "clips3d.json").write_text(json.dumps({"complete": True}))
    assert jobs.run_wrapper(run) == 0
    assert clips_job(run) is None and not hook.calls["launch"]
    assert status_line(run).startswith("skipped:")


# ================================================================================================ pending, never failing
def test_an_owner_pause_leaves_clips_pending_and_is_never_resumed(hook):
    run = hook.run()
    pause_line("pause", time.time() - 5.0)                             # the owner pauses while the run ends
    before = shared.pauses_log().read_text()
    assert jobs.run_wrapper(run) == 0
    assert (run / "exit_code").read_text() == "0\n"
    assert clips_job(run) is None and not hook.calls["preflight"]
    line = status_line(run)
    assert line.startswith("pending:") and "pause" in line
    assert shared.pauses_log().read_text() == before                  # nothing resumed, nothing written to the log
    text = (run / post_run.CLIPS3D_DIR / post_run.HOOK_STATUS).read_text()
    assert "retry:" in text and "post-clips3d --run-dir" in text


def test_a_session_pause_does_not_hold_the_clips(hook):
    run = hook.run()
    pause_line("pause", time.time() - 5.0, by="lead")
    assert jobs.run_wrapper(run) == 0
    assert clips_job(run) is not None
    wait_clips()


def test_a_busy_gpu_leaves_clips_pending(hook):
    hook.preflight_code = 11
    run = hook.run()
    assert jobs.run_wrapper(run) == 0
    assert (run / "exit_code").read_text() == "0\n"
    assert clips_job(run) is None and not hook.calls["launch"]
    line = status_line(run)
    assert line.startswith("pending:") and "preflight exit 11" in line


def test_the_tasks_cap_leaves_clips_pending(hook, tmp_path):
    (tmp_path / "tight").mkdir()
    hook.caps = settings(tmp_path / "tight", phase_cap=5.0, L0_11=0.05)     # under the clips job's 0.1 ask
    run = hook.run()
    assert jobs.run_wrapper(run) == 0
    assert (run / "exit_code").read_text() == "0\n"
    assert clips_job(run) is None and len(hook.calls["launch"]) == 1   # asked, and refused by the cap
    line = status_line(run)
    assert line.startswith("pending:") and "cap" in line


@pytest.mark.parametrize("clips_code, complete, word", [(11, False, "pending:"), (2, False, "failed:"),
                                                        (3, True, "failed:"), (0, False, "failed:")],
                         ids=["gpu_busy", "refused", "render_failed", "zero_but_incomplete"])
def test_the_clips_jobs_end_is_written_to_the_marker(hook, clips_code, complete, word):
    hook.clips_code, hook.clips_complete = clips_code, complete
    run = hook.run()
    assert jobs.run_wrapper(run) == 0
    assert wait_clips().exit_code == clips_code
    line = status_line(run)
    assert line.startswith(word) and f"exit {clips_code}" in line, line
    assert (run / "exit_code").read_text() == "0\n"                   # the training job's code never moves


def test_a_failing_hook_never_changes_the_training_jobs_exit_code(hook, monkeypatch, capsys):
    seen = {}

    def broken(run, *args, **kwargs):                  # what was recorded when the hook started, then it breaks
        seen["exit_code"] = (run / "exit_code").read_text()
        seen["ledger"] = shared.gpu_hours_log().read_text()
        raise RuntimeError("the hook broke")
    monkeypatch.setattr(post_run, "fire", broken)
    run = hook.run(gpu_h=0.3)
    assert jobs.run_wrapper(run) == 0
    assert seen["exit_code"] == (run / "exit_code").read_text() == "0\n"
    assert shared.gpu_hours_log().read_text() == seen["ledger"]       # the run's ledger rows: not one changed or added
    assert [json.loads(row)["job"] for row in seen["ledger"].splitlines()] and \
        {json.loads(row)["job"] for row in seen["ledger"].splitlines()} == {"train"}
    assert (run / "exit_code").read_text() == "0\n"
    job = state.read()["jobs"]["train"]
    assert job["exit_code"] == 0 and job["ended"] is not None
    printed = capsys.readouterr().out
    assert "post-run clips3d FAILED" in printed and "the hook broke" in printed
    assert jobs.verdict(job["exit_code"], 1.0, 0.0) == ("DONE", 0)    # (this process is the wrapper: no wait here)


# ================================================================================================ retry and status
def test_the_retry_line_launches_the_pending_clips(hook):
    pause_line("pause", time.time() - 5.0)
    run = hook.run()
    assert jobs.run_wrapper(run) == 0
    assert status_line(run).startswith("pending:")
    assert post_run.retry(run) == post_run.EXIT_REFUSED                # the training job still runs: refused
    wrapper_gone()
    assert post_run.retry(run) == post_run.EXIT_REFUSED                # still paused: still pending
    assert status_line(run).startswith("pending:") and clips_job(run) is None
    pause_line("resume", time.time())                                  # the owner resumes
    assert post_run.retry(run) == 0
    assert status_line(run).startswith("launched:")
    assert wait_clips().exit_code == 0 and status_line(run).startswith("done:")


def test_retry_refuses_a_run_that_did_not_end_with_0(hook, capsys):
    run = hook.run(exit_code=3)
    assert jobs.run_wrapper(run) == 0
    wrapper_gone()
    capsys.readouterr()
    assert post_run.retry(run) == post_run.EXIT_REFUSED and clips_job(run) is None
    assert "the training job exited 3, not 0" in capsys.readouterr().out


def test_a_failed_clips_job_with_complete_clips_stays_failed_on_retry(hook):
    """Exit 1 or 3 still writes clips3d.json complete; the clip script then refuses the folder, so a retry must not
    turn the failure into "skipped"."""
    hook.clips_code, hook.clips_complete = 3, True
    run = hook.run()
    assert jobs.run_wrapper(run) == 0
    assert wait_clips().exit_code == 3 and status_line(run).startswith("failed:")
    wrapper_gone()
    assert post_run.retry(run) == post_run.EXIT_REFUSED
    line = status_line(run)
    assert line.startswith("failed:") and "exited 3" in line and len(hook.calls["launch"]) == 1


def test_a_retry_while_the_clips_job_runs_touches_nothing(hook, capsys):
    hook.clips_sleep_s = 3.0
    run = hook.run()
    assert jobs.run_wrapper(run) == 0
    wrapper_gone()
    before = (run / post_run.CLIPS3D_DIR / post_run.HOOK_STATUS).read_text()
    capsys.readouterr()
    assert post_run.retry(run) == post_run.EXIT_REFUSED
    assert "clips job already running" in capsys.readouterr().out
    assert (run / post_run.CLIPS3D_DIR / post_run.HOOK_STATUS).read_text() == before
    assert len(hook.calls["launch"]) == 1 and len(hook.calls["preflight"]) == 1
    assert wait_clips().exit_code == 0 and status_line(run).startswith("done:")


def test_a_partial_clips_json_after_a_failure_is_drawn_again_on_retry(hook):
    hook.clips_code, hook.clips_complete = 3, False                    # the render failed: clips3d.json complete: false
    run = hook.run()
    assert jobs.run_wrapper(run) == 0
    assert wait_clips().exit_code == 3 and status_line(run).startswith("failed:")
    assert json.loads((run / post_run.CLIPS3D_DIR / "clips3d.json").read_text()) == {"complete": False}
    wrapper_gone()
    hook.clips_code, hook.clips_complete = 0, True                     # the second try works
    assert post_run.retry(run) == 0
    assert status_line(run).startswith("launched:")
    assert wait_clips().exit_code == 0 and status_line(run).startswith("done:")
    assert json.loads((run / post_run.CLIPS3D_DIR / "job.json").read_text())["launch"] == 2   # the same job, relaunched


def test_a_clips_job_never_fires_clips_of_its_own(hook, tmp_path):
    """Even a hand-edited job.json carrying both keys: a job with clips3d_for only reports its end; and the launcher
    refuses the two together."""
    other = tmp_path / "runs" / "the_run"
    run = hook.run(name="clipsjob")                                    # finishes 0 with a complete run of its own
    record = json.loads((run / "job.json").read_text())
    (run / "job.json").write_text(json.dumps(dict(record, post_clips3d=True, clips3d_for=str(other))))
    assert jobs.run_wrapper(run) == 0
    assert not hook.calls["launch"] and not hook.calls["preflight"]
    assert status_line(other).startswith("failed:")                    # its end went to the run it drew for
    assert not (run / post_run.CLIPS3D_DIR).exists()
    with pytest.raises(jobs.LaunchRefused, match="never starts clips of its own"):
        jobs.launch(TASK, "both", tmp_path / "both", ["true"], 0.0, 0.0, settings=hook.caps, post_clips3d=True,
                    clips3d_for=other)


def test_a_preflight_that_does_not_answer_leaves_clips_pending(hook, monkeypatch, tmp_path):
    """The real preflight() with a script that hangs (a child that keeps its output open, as a stuck nvidia-smi
    would): cut at PREFLIGHT_TIMEOUT_S, its whole process group killed, the hook says pending."""
    slow = tmp_path / "slow_preflight.sh"
    slow.write_text("#!/bin/bash\necho checking\nsleep 60\n")
    monkeypatch.setattr(post_run, "preflight", REAL_PREFLIGHT)
    monkeypatch.setattr(post_run, "PREFLIGHT_SCRIPT", slow)
    monkeypatch.setattr(post_run, "PREFLIGHT_TIMEOUT_S", 1.0)
    run = hook.run()
    started = time.monotonic()
    assert jobs.run_wrapper(run) == 0
    assert time.monotonic() - started < 15.0
    assert clips_job(run) is None and not hook.calls["launch"]
    line = status_line(run)
    assert line.startswith("pending:") and "preflight exit 124" in line
    assert "no answer within 1 s" in (run / post_run.CLIPS3D_DIR / post_run.PREFLIGHT_LOG).read_text()
    assert (run / "exit_code").read_text() == "0\n"


def test_the_status_reads_running_while_the_clips_job_lives_and_done_after(hook):
    hook.clips_sleep_s = 3.0
    run = hook.run()
    assert jobs.run_wrapper(run) == 0
    assert post_run.hook_state(run, state.read()["jobs"]) == "running"
    wait_clips()
    assert post_run.hook_state(run, state.read()["jobs"]) == "done"


def test_a_launched_marker_whose_clips_job_is_gone_reads_missing(tmp_path, monkeypatch):
    """A clips command that could not start (or a wrapper killed with it) never writes its end: status says missing."""
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    run = tmp_path / "runs" / "train"
    (run / post_run.CLIPS3D_DIR).mkdir(parents=True)
    (run / post_run.CLIPS3D_DIR / post_run.HOOK_STATUS).write_text("launched: job clips3d_train\n")
    assert post_run.hook_state(run, {}) == post_run.MISSING
    assert post_run.hook_state(tmp_path / "runs" / "other", {}) is None


@pytest.mark.parametrize("post, exit_code, clips, expected", [
    (True, "0\n", None, "missing"),                  # the wrapper was killed (or the machine rebooted) before the hook
    (True, "0\n", {"complete": False}, "missing"),   # a partial clips3d.json, nothing alive
    (True, "0\n", {"complete": True}, None),         # clips made (by hand): nothing to flag
    (True, "3\n", None, None),                       # the run failed: no clips owed
    (True, None, None, None),                        # no exit code yet: still running
    (False, "0\n", None, None),                      # the hook was off
], ids=["no_marker", "partial_clips", "clips_complete", "run_failed", "no_exit_code", "hook_off"])
def test_an_exit_0_run_with_the_hook_on_and_no_clips_reads_missing(tmp_path, monkeypatch, post, exit_code, clips,
                                                                   expected):
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    run = tmp_path / "runs" / "train"
    run.mkdir(parents=True)
    (run / "job.json").write_text(json.dumps({"name": "train", "post_clips3d": post}))
    if exit_code is not None:
        (run / "exit_code").write_text(exit_code)
    if clips is not None:
        (run / post_run.CLIPS3D_DIR).mkdir()
        (run / post_run.CLIPS3D_DIR / "clips3d.json").write_text(json.dumps(clips))
    assert post_run.hook_state(run, {}) == expected


def test_the_status_line_says_missing_after_a_killed_wrapper(hook, monkeypatch):
    run = hook.run()
    monkeypatch.setattr(jobs, "_post_run", lambda *args: None)        # the wrapper died before its hook ran
    assert jobs.run_wrapper(run) == 0
    wrapper_gone()
    lines = [line for line in jobs.status_lines() if line.startswith("train ")]
    assert len(lines) == 1 and "clips3d=missing" in lines[0]


def test_the_status_shows_the_clips_state(hook):
    pause_line("pause", time.time() - 5.0)
    run = hook.run()
    assert jobs.run_wrapper(run) == 0
    lines = [line for line in jobs.status_lines() if line.startswith("train ")]
    assert len(lines) == 1 and "clips3d=pending" in lines[0]


# ================================================================================================ the command line
def test_the_flag_is_recorded_and_replayed_and_a_failed_run_keeps_its_code(tmp_path, monkeypatch):
    """End to end through scripts/ste_job.py: --post-clips3d is in job.json and cmd.txt; a run that exits 3 starts no
    clips job and its waiter still returns 3, as without the flag."""
    shared_dir = tmp_path / "shared"
    env = tool_env(shared_dir)
    monkeypatch.setenv(shared.SHARED_ENV, str(shared_dir))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")
    caps = settings(tmp_path, phase_cap=5.0, L0_11=1.0)
    codes = {}
    for name, extra in (("flagged", ["--post-clips3d"]), ("plain", [])):
        run = tmp_path / "runs" / name
        cmd = [child_python(), "-c", "import sys, time\ntime.sleep(0.2)\nsys.exit(3)"]
        done = run_py([TOOL, "launch", "--task", TASK, "--name", name, "--run-dir", run, "--min-s", 0, "--gpu-h", 0,
                       "--settings", caps, "--beat-s", BEAT_S, *extra, "--", *cmd], env)
        assert done.returncode == 0, done.stderr
        record = json.loads((run / "job.json").read_text())
        assert record["post_clips3d"] is bool(extra)
        assert ("--post-clips3d" in (run / "cmd.txt").read_text()) is bool(extra)
        waited = run_py([TOOL, "wait", name, "--poll-s", "0.02"], env)
        codes[name] = waited.returncode
        assert (run / "exit_code").read_text() == "3\n"
        assert not (run / post_run.CLIPS3D_DIR).exists()
    assert codes == {"flagged": 3, "plain": 3}
    assert set(state.read()["jobs"]) == {"flagged", "plain"}            # no clips job was started
    log = (tmp_path / "runs" / "flagged" / "job.log").read_text()
    assert "post-run clips3d: not started (the training job exited 3, not 0)" in log
    retried = run_py([TOOL, "post-clips3d", "--run-dir", tmp_path / "runs" / "flagged"], env)
    assert retried.returncode == 2 and "exited 3" in retried.stdout + retried.stderr


@pytest.mark.parametrize("cmd, on", [
    (["/x/python", "scripts/ste_exploit_l012.py", "--variant", "base", "--side", "guard", "--run-dir", "r"], True),
    (["/x/python", "-u", "/abs/svg_training/scripts/ste_exploit_l012.py", "--side", "strike"], True),
    (["/x/python", "scripts/ste_exploit_l012.py", "--pilot", "--run-dir", "r"], False),       # writes pilot.json only
    (["/x/python", "scripts/ste_exploit_l012.py", "--run0", "--run-dir", "r"], False),        # run 0: no INFO batch
    (["/x/python", "scripts/ste_exploit_l012.py", "verdict", "--runs", "a,b"], False),
    (["/x/python", "scripts/ste_l5_clips3d.py", "--run-dir", "r"], False),
    (["/x/python", "scripts/ste_tier2_l013.py", "--run-dir", "r"], False),                    # no eval_info.npz
    (["/x/python", "scripts/ste_dummy_job.py"], False),
], ids=["run", "run_abs", "pilot", "run0", "verdict", "clips", "tier2", "dummy"])
def test_the_hook_is_on_by_default_for_the_training_drivers_runs(cmd, on):
    assert post_run.drives_training(cmd) is on


def test_the_default_is_recorded_and_no_post_clips3d_opts_out(tmp_path, monkeypatch):
    """Through scripts/ste_job.py: a command running scripts/ste_exploit_l012.py gets the hook with no flag (job.json,
    cmd.txt); --no-post-clips3d turns it off. The stand-in exits 0 without a finished run: the hook says skipped."""
    shared_dir = tmp_path / "shared"
    env = tool_env(shared_dir)
    monkeypatch.setenv(shared.SHARED_ENV, str(shared_dir))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")
    caps = settings(tmp_path, phase_cap=5.0, L0_11=1.0)
    for name, extra, on in (("auto", [], True), ("optout", ["--no-post-clips3d"], False)):
        run = tmp_path / "runs" / name
        cmd = [child_python(), "-c", "import sys\nsys.exit(0)", "scripts/ste_exploit_l012.py", "--side", "guard"]
        done = run_py([TOOL, "launch", "--task", TASK, "--name", name, "--run-dir", run, "--min-s", 0, "--gpu-h", 0,
                       "--settings", caps, "--beat-s", BEAT_S, *extra, "--", *cmd], env)
        assert done.returncode == 0, done.stderr
        assert json.loads((run / "job.json").read_text())["post_clips3d"] is on
        replay = (run / "cmd.txt").read_text()
        assert ("--post-clips3d" in replay) is on and ("--no-post-clips3d" in replay) is not on
        assert run_py([TOOL, "wait", name, "--poll-s", "0.02"], env).returncode == 0
        marker = run / post_run.CLIPS3D_DIR / post_run.HOOK_STATUS
        assert marker.exists() is on
        if on:
            assert marker.read_text().startswith("skipped:") and "results.json" in marker.read_text()
    both = run_py([TOOL, "launch", "--task", TASK, "--name", "x", "--run-dir", tmp_path / "x", "--min-s", 0, "--gpu-h",
                   0, "--post-clips3d", "--no-post-clips3d", "--", "true"], env)
    assert both.returncode == 2 and "not allowed with" in both.stderr


def test_end_to_end_the_real_preflight_and_the_real_clip_script_on_a_stub_run(tmp_path, monkeypatch):
    """Through scripts/ste_job.py with nothing replaced but nvidia-smi (a fake that lists no GPU process, as
    tests/_ste_tools.py's pause_script does): the training job exits 0 with a stub complete run, the wrapper runs the
    real scripts/isaac_preflight.sh and launches the real scripts/ste_l5_clips3d.py, which refuses the stub (no
    gates.toml: exit 2). The marker says failed, the training job's code stays 0. No GPU, no Isaac."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "nvidia-smi"
    fake.write_text("#!/bin/bash\n")
    fake.chmod(0o755)
    shared_dir = tmp_path / "shared"
    env = tool_env(shared_dir, PATH=f"{bin_dir}:{os.environ['PATH']}", CUDA_VISIBLE_DEVICES="")
    monkeypatch.setenv(shared.SHARED_ENV, str(shared_dir))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")
    caps = settings(tmp_path, phase_cap=5.0, L0_11=1.0)
    run = tmp_path / "runs" / "stub"
    code = ("import json, sys\nfrom pathlib import Path\nrun = Path(sys.argv[1])\n"
            "(run / 'results.json').write_text(json.dumps({'complete': True}))\n"
            "(run / 'agent_final.pt').write_bytes(b'weights')\n")
    cmd = [child_python(), "-c", code, str(run)]
    done = run_py([TOOL, "launch", "--task", TASK, "--name", "stub", "--run-dir", run, "--min-s", 0, "--gpu-h", 0,
                   "--settings", caps, "--beat-s", BEAT_S, "--post-clips3d", "--", *cmd], env)
    assert done.returncode == 0, done.stderr
    assert run_py([TOOL, "wait", "stub", "--poll-s", "0.02"], env).returncode == 0
    assert (run / "exit_code").read_text() == "0\n"
    out = run / post_run.CLIPS3D_DIR
    assert "preflight OK (exit 0)" in (out / post_run.PREFLIGHT_LOG).read_text()
    assert "post-run clips3d: launched clips3d_stub" in (run / "job.log").read_text()
    waited = run_py([TOOL, "wait", "clips3d_stub", "--poll-s", "0.02"], env, timeout_s=300)
    assert waited.returncode == 2, waited.stdout + waited.stderr                     # the clip script's refusal
    assert "has no gates.toml" in (out / "job.log").read_text()
    line = status_line(run)
    assert line.startswith("failed:") and "exit 2" in line
    assert (run / "exit_code").read_text() == "0\n"
    assert "clips3d=failed" in run_py([TOOL, "status", "--settings", caps], env).stdout


def test_the_hook_module_loads_no_pytorch():
    import subprocess
    from _proc import child_env
    code = "import sys\nimport svg_training.ste.post_run\nassert 'torch' not in sys.modules and 'numpy' not in sys.modules\n"
    done = subprocess.run([child_python(), "-c", code], env=child_env(str(ROOT / "source")), capture_output=True,
                          text=True)
    assert done.returncode == 0, done.stderr
