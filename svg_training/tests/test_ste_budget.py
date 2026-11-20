"""STE learning track, task L0.7: the GPU-hour ledger and the launch check (ste/budget.py).

The ledger is an append-only log in the shared folder: one line per CUDA interval of a job, under its task ID. Used
GPU-hours of a task, and of the phase, are the union of the intervals (jobs side by side count once) less the paused
time inside them: the arithmetic of ``nus/pauses.py::logged_gpu_hours``, imported. ``check_launch`` compares what is
used plus what is asked with the caps of ``configs/ste_learning.toml``. Every log here is made up."""
import json
import subprocess

import pytest

from _ste_tools import SOURCE, settings
from _proc import child_env, child_python
from svg_training.nus import pauses as nus_pauses
from svg_training.ste import budget, pauses, shared
from svg_training.ste.config import SETTINGS_FILE

T0 = 3_000_000.0
HOUR = 3600.0


@pytest.fixture(autouse=True)
def made_up_machine(tmp_path, monkeypatch):
    """A private shared folder, no legacy log, and a boot long before every made-up time."""
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")
    monkeypatch.setattr(pauses, "boot_time_s", lambda: 0.0)


def pause(start_h: float, end_h: float | None, pids: tuple | list = (1,)) -> None:
    """A pause and its resume (``end_h`` None: still open). ``pids``: the processes the pause stopped."""
    with shared.pauses_log().open("a") as stream:
        for event, hours in (("pause", start_h), ("resume", end_h)):
            if hours is not None:
                stream.write(json.dumps({"event": event, "time": T0 + hours * HOUR, "pids": list(pids), "by": "tester"}) + "\n")


RUN_A, RUN_B = "/runs/ste_l0/sweep_a", "/runs/ste_l0/sweep_b"     # two run folders (made-up paths)


def ran(task: str, job: str, start_h: float, end_h: float, device: str = "cuda", pids: list[int] | None = None,
        run_dir: str | None = None) -> bool:
    """A ledger line. ``pids=None``: a line without pids, as written before L07-C1 (every pause counts for it).
    ``run_dir=None``: a line without the run folder, as written before L07-I1 (never credited to a launch)."""
    return budget.log_interval(task, job, device, T0 + start_h * HOUR, T0 + end_h * HOUR, pids=pids, run_dir=run_dir)


# ------------------------------------------------------------------------------------------------ the ledger
def test_an_empty_ledger_has_used_nothing():
    assert budget.task_gpu_h("L0.11") == 0.0 and budget.phase_gpu_h("L0") == 0.0
    assert not shared.gpu_hours_log().exists()


def test_one_line_per_cuda_interval_and_cpu_jobs_log_nothing():
    assert ran("L0.11", "sweep", 0.0, 1.5) is True
    assert ran("L0.11", "sweep_cpu", 0.0, 9.0, device="cpu") is False             # a CPU job: no line
    assert ran("L0.2", "speed", 2.0, 2.5, device="cuda:0") is True
    rows = [json.loads(line) for line in shared.gpu_hours_log().read_text().splitlines()]
    assert rows == [{"group": "L0.11", "job": "sweep", "device": "cuda", "start": T0, "end": T0 + 1.5 * HOUR},
                    {"group": "L0.2", "job": "speed", "device": "cuda:0", "start": T0 + 2 * HOUR, "end": T0 + 2.5 * HOUR}]
    assert budget.task_gpu_h("L0.11") == 1.5 and budget.task_gpu_h("L0.2") == 0.5 and budget.task_gpu_h("L0.3") == 0.0
    assert budget.phase_gpu_h("L0") == 2.0


def test_an_interval_must_run_forwards():
    with pytest.raises(ValueError, match="end"):
        budget.log_interval("L0.11", "sweep", "cuda", T0 + 5.0, T0 + 4.0)
    assert not shared.gpu_hours_log().exists()


def test_jobs_side_by_side_count_once_and_paused_time_is_taken_off():
    """Two jobs of one task overlap for half an hour; the owner pauses for 0.4 h inside them and 1 h outside."""
    ran("L0.12", "seed0", 0.0, 2.0)
    ran("L0.12", "seed1", 1.5, 3.0)                    # union 0.0 to 3.0 = 3 h
    ran("L0.12", "seed2", 5.0, 6.0)                    # + 1 h
    pause(1.8, 2.2)                                    # inside the union: 0.4 h off
    pause(3.5, 4.5)                                    # nothing ran then: nothing off
    assert budget.task_gpu_h("L0.12") == pytest.approx(3.6)
    assert budget.task_gpu_h("L0.12") == pytest.approx(                               # the NUS module on the same files
        nus_pauses.logged_gpu_hours(shared.gpu_hours_log(), "L0.12", shared.pauses_log()))


def test_the_phase_is_the_union_over_its_tasks():
    """Two tasks side by side for the same two hours used two GPU-hours of the phase, not four."""
    ran("L0.11", "sweep", 0.0, 2.0)
    ran("L0.2", "speed", 0.0, 2.0)
    ran("L0.13", "probe", 3.0, 4.0)
    ran("L9.9", "another_phase", 10.0, 20.0)           # not a task of phase L0
    pause(3.25, 3.75)
    assert budget.task_gpu_h("L0.11") == 2.0 and budget.task_gpu_h("L0.2") == 2.0
    assert budget.task_gpu_h("L0.13") == pytest.approx(0.5)
    assert budget.phase_gpu_h("L0") == pytest.approx(2.5)


def test_a_running_job_is_counted_beat_by_beat():
    """The wrapper appends one line per beat while a job runs; touching lines add up to one interval."""
    for minute in range(90):
        ran("L0.13", "probe", minute / 60, (minute + 1) / 60)
    assert budget.task_gpu_h("L0.13") == pytest.approx(1.5)


# ------------------------------------------------------------------------------------------------ L07-C1: whose pause
def test_a_ledger_line_records_the_pids_of_the_job():
    assert ran("L0.12", "seed0", 0.0, 1.0, pids=[11])
    assert json.loads(shared.gpu_hours_log().read_text())["pids"] == [11]


@pytest.mark.parametrize("pids, used_h", [([], 3.0), ([12], 3.0), ([11], 2.0), ([12, 11], 2.0)])
def test_a_pause_takes_hours_off_only_the_jobs_it_stopped(pids, used_h):
    """Job seed0 (command pid 11) ran 3 h; the owner paused for 1 h of them. Only a pause that stopped pid 11 gives
    the hour back: one that stopped nothing or another job left seed0 running on the GPU."""
    ran("L0.12", "seed0", 0.0, 3.0, pids=[11])
    pause(1.0, 2.0, pids)
    assert budget.task_gpu_h("L0.12") == pytest.approx(used_h)
    assert budget.job_gpu_h("L0.12", "seed0") == pytest.approx(used_h)
    assert budget.phase_gpu_h("L0") == pytest.approx(used_h)


def test_qc_reproduction_an_open_pause_that_stopped_nothing_does_not_hide_the_hours(tmp_path):
    """The QC failure scenario: the owner paused with nothing running (``pids: []``) and never resumed; a job launched
    later ran on the GPU. Before the fix its hours read 0.000 and the next launch check passed."""
    path = settings(tmp_path, 19.0, L0_11=3.0)
    pause(0.0, None, [])
    ran("L0.11", "sweep", 1.0, 3.5, pids=[11])
    assert budget.task_gpu_h("L0.11") == pytest.approx(2.5)
    with pytest.raises(budget.BudgetError, match="used 2.500"):
        budget.check_launch("L0.11", 1.0, settings=path)


def test_a_paused_sibling_takes_no_time_off_the_job_that_ran_on():
    """Two jobs side by side, 0 to 2 h; the owner's pause from 0.5 to 1.5 h stopped only seed0. The GPU was busy all
    2 h (seed1 ran): the union is 2 h, seed0 used 1 h and seed1 2 h. Union first, pause after would give 1 h."""
    ran("L0.12", "seed0", 0.0, 2.0, pids=[11])
    ran("L0.12", "seed1", 0.0, 2.0, pids=[12])
    pause(0.5, 1.5, [11])
    assert budget.task_gpu_h("L0.12") == pytest.approx(2.0)
    assert budget.job_gpu_h("L0.12", "seed0") == pytest.approx(1.0)
    assert budget.job_gpu_h("L0.12", "seed1") == pytest.approx(2.0)
    pause(1.75, 1.9, [11, 12])                                                        # both stopped: 0.15 h off
    assert budget.task_gpu_h("L0.12") == pytest.approx(1.85)


def test_a_line_without_pids_still_loses_every_pause():
    """Legacy rule: a ledger line written before L07-C1 carries no pids, so it cannot be matched; it keeps the rule it
    was written under (every pause counts), the same numbers as before."""
    ran("L0.12", "old", 0.0, 3.0)
    pause(1.0, 2.0, [])
    assert budget.task_gpu_h("L0.12") == pytest.approx(2.0)
    assert budget.task_gpu_h("L0.12") == pytest.approx(
        nus_pauses.logged_gpu_hours(shared.gpu_hours_log(), "L0.12", shared.pauses_log()))


def test_a_torn_line_is_skipped_and_reported(capsys):
    ran("L0.11", "sweep", 0.0, 1.0)
    with shared.gpu_hours_log().open("a") as stream:
        stream.write('{"group": "L0.11", "job": "sw')
    assert budget.task_gpu_h("L0.11") == 1.0
    assert "1 unreadable line" in capsys.readouterr().err


# ------------------------------------------------------------------------------------------------ the launch check
def test_the_committed_caps():
    """configs/ste_learning.toml as committed: L0.11 has 3 GPU-h, L0.7 has none, the phase has 19."""
    usage = budget.check_launch("L0.11", 3.0)
    assert usage == budget.Usage(task_cap_gpu_h=3.0, task_used_gpu_h=0.0, phase_cap_gpu_h=19.0, phase_used_gpu_h=0.0)
    assert budget.check_launch("L0.7", 0.0).task_cap_gpu_h == 0.0                     # a CPU job asks for nothing
    with pytest.raises(budget.BudgetError, match=r"task L0\.11.*cap 3\.0 GPU-h.*used 0\.000.*asked 3\.1"):
        budget.check_launch("L0.11", 3.1)
    with pytest.raises(budget.BudgetError, match=r"task L0\.7.*cap 0\.0 GPU-h.*asked 0\.5"):
        budget.check_launch("L0.7", 0.5)
    assert budget.check_launch("L0.11", 3.0, settings=SETTINGS_FILE).phase_cap_gpu_h == 19.0


def test_refused_when_the_task_cap_would_be_exceeded(tmp_path):
    path = settings(tmp_path, 19.0, L0_11=3.0, L0_12=6.0)
    ran("L0.11", "sweep", 0.0, 2.0)
    assert budget.check_launch("L0.11", 1.0, settings=path).task_used_gpu_h == 2.0           # exactly the cap: allowed
    with pytest.raises(budget.BudgetError) as refused:
        budget.check_launch("L0.11", 1.25, settings=path)
    message = str(refused.value)
    assert "task L0.11" in message and "cap 3.0 GPU-h" in message and "used 2.000" in message and "asked 1.25" in message
    assert "budget.task_cap_gpu_h" in message and path.name in message
    assert budget.check_launch("L0.12", 6.0, settings=path).phase_used_gpu_h == 2.0           # another task: its own cap


def test_a_job_relaunched_with_the_same_line_is_not_charged_twice(tmp_path):
    """The hours asked for are the job's total over all its launches (its own cap travels in its checkpoint). A job
    that asked for the task's whole cap and used 2 of the 3 hours before a power cut must be able to resume with the
    SAME line (same name, same run folder): only the hour it has not used yet is new. Another job asking for 3 is
    still refused."""
    path = settings(tmp_path, 19.0, L0_11=3.0)
    ran("L0.11", "sweep", 0.0, 2.0, run_dir=RUN_A)
    assert budget.job_gpu_h("L0.11", "sweep") == 2.0 and budget.job_gpu_h("L0.11", "other") == 0.0
    assert budget.job_gpu_h("L0.12", "sweep") == 0.0                                  # the same name under another task
    with pytest.raises(budget.BudgetError, match=r"task L0\.11.*cap 3\.0 GPU-h.*used 2\.000.*asked 3\.0"):
        budget.check_launch("L0.11", 3.0, settings=path)                              # the reproduction: no job named
    assert budget.check_launch("L0.11", 3.0, settings=path, job="sweep", run_dir=RUN_A).task_used_gpu_h == 2.0
    with pytest.raises(budget.BudgetError, match="asked 3.0"):
        budget.check_launch("L0.11", 3.0, settings=path, job="other", run_dir=RUN_A)
    assert budget.check_launch("L0.11", 1.0, settings=path, job="other", run_dir=RUN_A).task_used_gpu_h == 2.0
    with pytest.raises(budget.BudgetError) as refused:                                # asks for more than it did before
        budget.check_launch("L0.11", 3.5, settings=path, job="sweep", run_dir=RUN_A)
    assert "asked 3.5" in str(refused.value) and "2.000 of them already used by job sweep" in str(refused.value)
    ran("L0.11", "sweep", 2.0, 3.25, run_dir=RUN_A)                                   # it overran what it asked for
    assert budget.check_launch("L0.11", 3.0, settings=path, job="sweep", run_dir=RUN_A).task_used_gpu_h == 3.25


# ------------------------------------------------------------------------------------------------ L07-I1: whose credit
def test_a_ledger_line_records_the_run_folder():
    assert ran("L0.11", "sweep", 0.0, 1.0, run_dir=RUN_A)
    assert json.loads(shared.gpu_hours_log().read_text())["run_dir"] == RUN_A


def test_qc_reproduction_a_new_run_under_an_old_name_gets_no_credit(tmp_path):
    """L07-I1, the QC scenario: job "sweep" finished after 2.9 GPU-h (task cap 3.0). A NEW run folder under the same
    name asking 3.0 was accepted (charged 0.1), so the task could reach 5.9 GPU-h. A rerun is a new run: no credit.
    The same run folder (a resume) keeps its credit."""
    path = settings(tmp_path, 19.0, L0_11=3.0)
    ran("L0.11", "sweep", 0.0, 2.9, run_dir=RUN_A)
    with pytest.raises(budget.BudgetError, match=r"used 2\.900.*asked 3\.0"):
        budget.check_launch("L0.11", 3.0, settings=path, job="sweep", run_dir=RUN_B)
    assert budget.check_launch("L0.11", 3.0, settings=path, job="sweep", run_dir=RUN_A).task_used_gpu_h == pytest.approx(2.9)
    assert budget.check_launch("L0.11", 0.1, settings=path, job="sweep", run_dir=RUN_B).task_used_gpu_h == pytest.approx(2.9)
    assert budget.job_gpu_h("L0.11", "sweep", run_dir=RUN_A) == pytest.approx(2.9)
    assert budget.job_gpu_h("L0.11", "sweep", run_dir=RUN_B) == 0.0


def test_a_line_without_a_run_folder_counts_as_used_but_is_never_credited(tmp_path):
    """Legacy rule: a line written before L07-I1 cannot be tied to a run folder. It still counts as used; it is not
    credited to any launch (the safe side: a resume may be refused, a cap is never passed)."""
    path = settings(tmp_path, 19.0, L0_11=3.0)
    ran("L0.11", "sweep", 0.0, 2.0)
    assert budget.task_gpu_h("L0.11") == 2.0 and budget.job_gpu_h("L0.11", "sweep", run_dir=RUN_A) == 0.0
    with pytest.raises(budget.BudgetError, match=r"used 2\.000.*asked 3\.0"):
        budget.check_launch("L0.11", 3.0, settings=path, job="sweep", run_dir=RUN_A)


def test_a_job_name_without_its_run_folder_is_a_mistake():
    """Credit by name alone was the I1 failure: the name and the run folder go together."""
    with pytest.raises(ValueError, match="run_dir"):
        budget.check_launch("L0.11", 1.0, job="sweep")
    with pytest.raises(ValueError, match="job"):
        budget.check_launch("L0.11", 1.0, run_dir=RUN_A)


def test_paused_time_gives_the_hours_back(tmp_path):
    path = settings(tmp_path, 19.0, L0_11=3.0)
    ran("L0.11", "sweep", 0.0, 3.0)
    with pytest.raises(budget.BudgetError, match="used 3.000"):
        budget.check_launch("L0.11", 0.5, settings=path)
    pause(1.0, 2.0)                                    # the owner had paused for one of those three hours
    assert budget.check_launch("L0.11", 0.5, settings=path).task_used_gpu_h == pytest.approx(2.0)


def test_refused_when_the_phase_cap_would_be_exceeded(tmp_path):
    """The task caps fit the phase cap (the loader checks), so the phase cap bites only after a task overran its own:
    L0.11 used 4 h of its 3; L0.12 asks for its full 2; the phase cap of 5 refuses."""
    path = settings(tmp_path, 5.0, L0_11=3.0, L0_12=2.0)
    ran("L0.11", "sweep", 0.0, 4.0)
    with pytest.raises(budget.BudgetError) as refused:
        budget.check_launch("L0.12", 2.0, settings=path)
    message = str(refused.value)
    assert "phase L0" in message and "cap 5.0 GPU-h" in message and "used 4.000" in message and "asked 2.0" in message
    assert "budget.phase_cap_gpu_h" in message
    assert budget.check_launch("L0.12", 1.0, settings=path) == budget.Usage(2.0, 0.0, 5.0, 4.0)


def test_an_exact_fit_is_allowed_despite_binary_rounding(tmp_path):
    """0.1 used + 0.2 asked is 0.30000000000000004 in binary floats; the cap is 0.3 and the launch fits."""
    path = settings(tmp_path, 19.0, L0_5=0.3)
    ran("L0.5", "look", 0.0, 0.1)
    assert budget.check_launch("L0.5", 0.2, settings=path).task_used_gpu_h == pytest.approx(0.1)
    with pytest.raises(budget.BudgetError):
        budget.check_launch("L0.5", 0.21, settings=path)


@pytest.mark.parametrize("task, asked, message", [
    ("L0.99", 1.0, "L0.99"), ("L1.1", 0.0, "L1.1"), ("L0.11", -1.0, "asked"), ("L0.11", float("nan"), "asked"),
    ("L0.11", float("inf"), "asked"),
])
def test_an_unknown_task_or_a_senseless_request_is_refused(task, asked, message):
    with pytest.raises(budget.BudgetError, match=message):
        budget.check_launch(task, asked)


def test_importing_loads_no_pytorch():
    code = "import sys\nimport svg_training.ste.budget\nassert 'torch' not in sys.modules and 'numpy' not in sys.modules\n"
    done = subprocess.run([child_python(), "-c", code], env=child_env(str(SOURCE)), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
