"""STE learning track, task L0.7: the launcher, the waiter and the status list (scripts/ste_job.py, ste/jobs.py).

``launch`` starts a command detached, behind a thin wrapper that records the command's own exit code; ``wait`` blocks
until the job has ended and exits with the job's exit code; ``status`` lists the jobs. A job is identified by pid,
process start time and boot id, never by its name or command line. Each failure of 20 Nov 2026 is reproduced here and
shown caught:

* F-a a watcher that searched command lines matched its own shell and never fired;
* F-b a background command reported the exit code of its last command (0), not the job's;
* F-c a run that ended in 3 minutes instead of 19 raised no flag;
* F-d after a power cut a stale pid must read "dead (previous boot)", and the same command must resume."""
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from _ste_tools import (ROOT, SCRIPTS, SOURCE, WAIT_S, kill_group, pause_script, proc_state, reap, run_py, settings,
                        tool_env, wait_for)
from _proc import child_env, child_python
from svg_training.ste import budget, jobs, pauses, run_contract as rc, shared, state

TOOL = SCRIPTS / "ste_job.py"
DUMMY = SCRIPTS / "ste_dummy_job.py"
POLL = "0.02"
OTHER_BOOT = "00000000-0000-4000-8000-000000000000"
DISPLAY_HALF_STEP_S = 0.05     # the waiter prints durations to 0.1 s


class Bench:
    """One private shared folder, the tool run as a real command line, and every started process cleaned up."""

    def __init__(self, tmp_path: Path, monkeypatch):
        self.tmp, self.shared = tmp_path, tmp_path / "shared"
        self.env = tool_env(self.shared)
        monkeypatch.setenv(shared.SHARED_ENV, str(self.shared))       # so this process reads the same state file
        monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")
        self.waiters: list[subprocess.Popen] = []

    def run_dir(self, name: str) -> Path:
        return self.tmp / "runs" / name

    def dummy(self, name: str, steps: int = 20, step_s: float = 0.03, cap_s: float = 600.0, every: int = 2,
              extra: tuple = ()) -> list[str]:
        return [child_python(), str(DUMMY), "--run-dir", str(self.run_dir(name)), "--steps", str(steps), "--step-s",
                str(step_s), "--cap-s", str(cap_s), "--checkpoint-every", str(every), *map(str, extra)]

    def launch(self, name: str, cmd: list[str], min_s: float = 0.0, gpu_h: float = 0.0, task: str = "L0.7",
               extra: tuple = ()) -> subprocess.CompletedProcess:
        return run_py([TOOL, "launch", "--task", task, "--name", name, "--run-dir", self.run_dir(name), "--min-s", min_s,
                       "--gpu-h", gpu_h, *extra, "--", *cmd], self.env)

    def wait(self, name: str) -> subprocess.CompletedProcess:
        return run_py([TOOL, "wait", name, "--poll-s", POLL], self.env)

    def start_wait(self, name: str) -> subprocess.Popen:
        waiter = subprocess.Popen([child_python(), str(TOOL), "wait", name, "--poll-s", POLL], env=self.env, cwd=ROOT,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.waiters.append(waiter)
        return waiter

    def status(self) -> str:
        done = run_py([TOOL, "status"], self.env)
        assert done.returncode == 0, done.stderr
        return done.stdout

    def job(self, name: str) -> dict:
        return state.read()["jobs"][name]

    def step(self, name: str) -> int:
        path = self.run_dir(name) / rc.CHECKPOINT_NAME
        return json.loads(path.read_text())["step"] if path.exists() else 0

    def child(self, name: str) -> int:
        wait_for(lambda: self.job(name)["child_pid"] is not None, what="the wrapper to record its command's pid")
        return self.job(name)["child_pid"]

    def clean_up(self) -> None:
        for waiter in self.waiters:
            reap(waiter)
        try:
            recorded = state.read()["jobs"]
        except state.StateError:
            return
        for job in recorded.values():
            for pid, started in ((job["pid"], job["pid_start"]), (job["child_pid"], job["child_start"])):
                if pid is not None and job["boot_id"] == state.boot_id() and state.process_start_time(pid) == started:
                    kill_group(pid)
        wait_for(lambda: not any(state.job_alive(job) for job in state.read()["jobs"].values()), what="the clean-up")


@pytest.fixture()
def bench(tmp_path, monkeypatch):
    made = Bench(tmp_path, monkeypatch)
    yield made
    made.clean_up()


def exit_cmd(code: int, sleep_s: float = 0.0) -> list[str]:
    return [child_python(), "-c", f"import sys, time\ntime.sleep({sleep_s})\nprint('bye', flush=True)\nsys.exit({code})"]


def line_of(done: subprocess.CompletedProcess) -> str:
    lines = done.stdout.splitlines()
    assert len(lines) == 1, (done.stdout, done.stderr)               # the waiter prints ONE line
    return lines[0]


# ================================================================================================ launch and wait
def test_launch_records_the_job_and_wait_returns_its_exit_code(bench):
    cmd = bench.dummy("drill")
    before = time.time()
    launched = bench.launch("drill", cmd)
    assert launched.returncode == 0, launched.stderr
    job = bench.job("drill")
    assert f"pid={job['pid']}" in launched.stdout and "L0.7 drill" in launched.stdout
    assert job["task"] == "L0.7" and job["cmd"] == cmd and job["launch"] == 1 and job["boot_id"] == state.boot_id()
    assert before <= job["started"] <= time.time() and job["expected_min_s"] == 0.0 and job["gpu_h"] == 0.0
    assert job["run_dir"] == str(bench.run_dir("drill")) and job["log"] == str(bench.run_dir("drill") / "job.log")
    assert job["cwd"] == str(ROOT)
    assert state.read()["phase"] == "L0"

    done = bench.wait("drill")
    assert done.returncode == rc.EXIT_DONE == 0, done.stderr
    assert re.fullmatch(r"L0\.7 drill DONE exit=0 duration=\d+\.\ds effective=\d+\.\ds", line_of(done))

    run = bench.run_dir("drill")
    assert (run / "exit_code").read_text() == "0\n"
    assert json.loads((run / "result.json").read_text()) == {"steps": 20, "total": 210.0}
    assert "[dummy] done: 20 steps" in (run / "job.log").read_text()
    record = json.loads((run / "job.json").read_text())
    assert record["name"] == "drill" and record["pid"] == job["pid"] and record["pid_start"] == job["pid_start"]
    relaunch = (run / "cmd.txt").read_text()
    assert "ste_job.py launch --task L0.7 --name drill" in relaunch and "ste_dummy_job.py" in relaunch
    rows = [json.loads(line) for line in (run / "launches.jsonl").read_text().splitlines()]
    assert [(row["event"], row["launch"]) for row in rows] == [("launch", 1), ("end", 1)] and rows[1]["exit_code"] == 0
    ended = bench.job("drill")
    assert ended["exit_code"] == 0 and ended["ended"] >= ended["started"] and ended["child_pid"] is not None
    assert not state.job_alive(ended)
    assert not shared.gpu_hours_log().exists()                       # a CPU job logs no GPU time


# ================================================================================================ cmd.txt (L07-I2)
ENV_KEYS = ("PYTHONPATH", "CUDA_VISIBLE_DEVICES", "PYTORCH_CUDA_ALLOC_CONF", "SVG_SHARED_DIR", "SVG_PAUSE_LEGACY_LOGS")
ODD_VALUE = "expandable_segments:True $HOME 'quoted' x"          # a space, a $, quotes: must arrive as written


def env_dump_cmd(out: Path) -> list[str]:
    """A command that appends its own values of ENV_KEYS (None when unset) as one JSON line to ``out``."""
    code = (f"import json, os\nwith open({str(out)!r}, 'a') as f:\n"
            f"    f.write(json.dumps({{k: os.environ.get(k) for k in {ENV_KEYS!r}}}) + '\\n')\n")
    return [child_python(), "-c", code]


def test_the_relaunch_line_sets_or_unsets_every_recorded_variable(tmp_path):
    """L07-I2, the line alone (no launch, so no shared folder is touched): a variable set at launch is set again to the
    same text, one that was absent is unset (``env -u``), the ``-u`` options come before the assignments, and a
    polluted shell running the line gives the command exactly the launch's values."""
    recorded = {"CUDA_VISIBLE_DEVICES": "", "PYTORCH_CUDA_ALLOC_CONF": ODD_VALUE, "SVG_SHARED_DIR": str(tmp_path / "s p")}
    out = tmp_path / "env.jsonl"
    line = jobs.relaunch_line(tmp_path, env_dump_cmd(out), recorded)
    words = shlex.split(line)
    assert words[:4] == ["cd", str(tmp_path), "&&", "env"]
    unset = [words[i + 1] for i, word in enumerate(words) if word == "-u"]
    assert sorted(unset) == sorted(set(jobs.RECORDED_ENV) - set(recorded))
    assert "PYTHONPATH" in unset and "SVG_PAUSE_LEGACY_LOGS" in unset
    assigned = [word for word in words if "=" in word.split("\n")[0] and word.split("=")[0] in jobs.RECORDED_ENV]
    assert assigned == [f"{key}={value}" for key, value in recorded.items()]
    assert max(i for i, word in enumerate(words) if word == "-u") < words.index(assigned[0])
    polluted = dict(os.environ, PYTHONPATH="/nonexistent/ros/jazzy", CUDA_VISIBLE_DEVICES="0", SVG_PAUSE_LEGACY_LOGS="x")
    polluted.pop("PYTORCH_CUDA_ALLOC_CONF", None)
    done = subprocess.run(["bash", "-c", line], env=polluted, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert json.loads(out.read_text()) == {**{key: None for key in ENV_KEYS}, **recorded}


def test_cmd_txt_replays_the_launch_environment_in_a_polluted_shell(bench, tmp_path):
    """L07-I2 end to end (QC): after a reboot ``bash <run>/cmd.txt`` runs in a new shell. That shell may carry ROS's
    PYTHONPATH, lack PYTORCH_CUDA_ALLOC_CONF, expose GPU 0 and point SVG_SHARED_DIR elsewhere. The job's command
    must see the first launch's values, and launch 2 must land in the recorded state.json."""
    run = bench.run_dir("envjob")
    first_env = dict(bench.env, CUDA_VISIBLE_DEVICES="", PYTORCH_CUDA_ALLOC_CONF=ODD_VALUE)
    first_env.pop("PYTHONPATH")                                             # the track's rule: unset at launch
    out = run / "env.jsonl"
    first = run_py([TOOL, "launch", "--task", "L0.7", "--name", "envjob", "--run-dir", run, "--min-s", 0.0, "--gpu-h",
                    0.0, "--", *env_dump_cmd(out)], first_env)
    assert first.returncode == 0, first.stderr
    assert bench.wait("envjob").returncode == 0
    elsewhere = tmp_path / "elsewhere"
    polluted = dict(os.environ, PYTHONPATH="/nonexistent/ros/jazzy", CUDA_VISIBLE_DEVICES="0",
                    SVG_SHARED_DIR=str(elsewhere))
    polluted.pop("PYTORCH_CUDA_ALLOC_CONF", None)
    polluted.pop("SVG_PAUSE_LEGACY_LOGS", None)
    line_1 = (run / "cmd.txt").read_text().split("\n", 1)[1]                   # all but the comment line
    again = subprocess.run(["bash", str(run / "cmd.txt")], env=polluted, cwd=tmp_path, capture_output=True, text=True,
                           timeout=WAIT_S)
    assert again.returncode == 0 and "launch=2" in again.stdout, (again.stdout, again.stderr)
    assert bench.job("envjob")["launch"] == 2 and not elsewhere.exists()    # the recorded state.json, nothing else
    assert bench.wait("envjob").returncode == 0
    seen = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(seen) == 2 and seen[0] == seen[1]
    assert seen[0] == {"PYTHONPATH": None, "CUDA_VISIBLE_DEVICES": "", "PYTORCH_CUDA_ALLOC_CONF": ODD_VALUE,
                       "SVG_SHARED_DIR": str(bench.shared), "SVG_PAUSE_LEGACY_LOGS": ""}
    assert (run / "cmd.txt").read_text().split("\n", 1)[1] == line_1         # the same line again


def test_a_relaunch_with_another_shared_folder_is_refused(bench, tmp_path):
    """L07-I2: the run folder records the shared folder of its launch (state.json, GPU-hour ledger, pause log). A
    relaunch that would use another one would count its hours and its state somewhere nobody looks: refused."""
    assert bench.launch("homed", bench.dummy("homed", steps=4)).returncode == 0
    assert bench.wait("homed").returncode == 0
    assert json.loads((bench.run_dir("homed") / "job.json").read_text())["shared_dir"] == str(bench.shared.resolve())
    other = tmp_path / "other_shared"
    moved = run_py([TOOL, "launch", "--task", "L0.7", "--name", "homed", "--run-dir", bench.run_dir("homed"), "--min-s",
                    0.0, "--gpu-h", 0.0, "--", *bench.dummy("homed", steps=4)], dict(bench.env, SVG_SHARED_DIR=str(other)))
    assert moved.returncode == rc.EXIT_REFUSED and moved.stdout == ""
    assert str(bench.shared.resolve()) in moved.stderr and str(other) in moved.stderr and "cmd.txt" in moved.stderr
    assert len(moved.stderr.splitlines()) == 1, moved.stderr
    assert not other.exists() and json.loads((bench.run_dir("homed") / "job.json").read_text())["launch"] == 1
    assert bench.launch("homed", bench.dummy("homed", steps=4)).returncode == 0     # the recorded folder: goes ahead
    assert bench.wait("homed").returncode == 0


def test_the_job_runs_detached_in_its_own_session(bench):
    """The launcher has returned; the job runs on as the leader of its own session, with its command inside it."""
    assert bench.launch("detached", bench.dummy("detached", steps=100_000)).returncode == 0
    job = bench.job("detached")
    child = bench.child("detached")
    assert state.job_status(job) == state.ALIVE
    assert os.getsid(job["pid"]) == job["pid"] != os.getsid(0) and os.getsid(child) == job["pid"]
    assert job["pid_start"] == state.process_start_time(job["pid"])
    wrapper_args = Path(f"/proc/{job['pid']}/cmdline").read_text().split("\0")
    assert wrapper_args[1:4] == [str(TOOL), "_run", str(bench.run_dir("detached"))]      # no job command on its line
    assert Path(f"/proc/{child}/cmdline").read_text().split("\0")[:-1] == job["cmd"]


def test_f_b_the_waiter_returns_the_jobs_own_exit_code(bench, tmp_path):
    """F-b. The reproduction: the shell line used on 20 Nov reports 0 for a command that exited 7. The waiter's exit
    status is the job's."""
    log = tmp_path / "log"
    old_way = subprocess.run(["bash", "-c", f'{sys.executable} -c "import sys; sys.exit(7)" > {log}; echo "exit $?"; tail {log}'],
                             capture_output=True, text=True)
    assert old_way.returncode == 0 and "exit 7" in old_way.stdout       # the failure: status 0, the 7 only in the text

    assert bench.launch("fails", exit_cmd(7)).returncode == 0
    done = bench.wait("fails")
    assert done.returncode == 7
    assert line_of(done).startswith("L0.7 fails FAILED exit=7 duration=")
    assert (bench.run_dir("fails") / "exit_code").read_text() == "7\n"
    for code, word in ((rc.EXIT_CAP, "CAP"), (rc.EXIT_NONFINITE, "NONFINITE"), (rc.EXIT_REFUSED, "REFUSED")):
        assert bench.launch(f"code{code}", exit_cmd(code)).returncode == 0
        done = bench.wait(f"code{code}")
        assert done.returncode == code and f" {word} exit={code} " in line_of(done)


def test_f_c_a_job_that_ends_much_too_early_is_flagged(bench):
    """F-c. A job expected to take at least 60 s that is over in a moment: exit code 0 must not pass in silence."""
    assert bench.launch("quick", exit_cmd(0), min_s=60.0).returncode == 0
    done = bench.wait("quick")
    assert done.returncode == jobs.EXIT_ENDED_EARLY == 20
    assert re.fullmatch(r"L0\.7 quick ENDED_EARLY exit=0 \(DONE\) duration=\d+\.\ds effective=\d+\.\ds expected_min=60\.0s",
                        line_of(done))


def test_f_c_early_and_failing_is_flagged_and_keeps_the_jobs_code(bench):
    """The real case of 20 Nov was early AND failing: the flag is printed, the status stays the job's own (F-b)."""
    assert bench.launch("quick_bad", exit_cmd(7), min_s=60.0).returncode == 0
    done = bench.wait("quick_bad")
    assert done.returncode == 7
    assert " ENDED_EARLY exit=7 (FAILED) " in line_of(done) and line_of(done).endswith("expected_min=60.0s")


def test_a_job_that_lasts_its_expected_minimum_is_not_flagged(bench):
    assert bench.launch("long_enough", exit_cmd(0, sleep_s=0.4), min_s=0.3).returncode == 0
    done = bench.wait("long_enough")
    assert done.returncode == 0 and " DONE exit=0 " in line_of(done)


def test_f_a_searching_command_lines_matches_the_searcher_itself():
    """F-a, the reproduction: no job with this marker exists, yet the search "finds" one: the shell that runs the
    search carries the marker on its own command line. A loop "until the search finds nothing" never ends."""
    marker = f"no_such_job_{uuid.uuid4().hex}"
    done = subprocess.run(["bash", "-c", f"pgrep -f '{marker}'; echo \"status $?\""], capture_output=True, text=True)
    assert "status 0" in done.stdout and len(done.stdout.split()) == 3       # one pid "found", then "status 0"


def test_f_a_the_waiter_returns_only_when_the_job_ends_though_its_own_command_line_names_the_job(bench):
    name = f"sweep_{uuid.uuid4().hex}"
    assert bench.launch(name, bench.dummy(name, steps=100_000)).returncode == 0
    waiter = bench.start_wait(name)
    assert name in Path(f"/proc/{waiter.pid}/cmdline").read_text()          # the waiter's command line holds the name
    wait_for(lambda: bench.step(name) >= 4, what="the job to make progress")
    seen = bench.step(name)
    wait_for(lambda: bench.step(name) >= seen + 6, what="more progress")
    assert waiter.poll() is None                                           # the job runs: the waiter still waits
    os.kill(bench.job(name)["pid"], signal.SIGINT)                         # to the recorded pid: the wrapper passes it on
    assert waiter.wait(timeout=WAIT_S) == rc.EXIT_INTERRUPTED
    out = waiter.stdout.read()
    assert out.startswith(f"L0.7 {name} INTERRUPTED exit=4 ") and len(out.splitlines()) == 1
    assert (bench.run_dir(name) / "exit_code").read_text() == "4\n" and not state.job_alive(bench.job(name))
    assert f"stopped (interrupted) at step {bench.step(name)}" in (bench.run_dir(name) / "job.log").read_text()


def test_no_process_is_ever_found_by_name():
    """The track's scripts and package never search command lines or signal by name (F-a). scripts/gpu_pause.sh, the
    owner's pause tool from the NUS port, is outside this rule: it keeps its pattern search, with its own guards."""
    files = sorted(SCRIPTS.glob("ste_*")) + sorted((SOURCE / "svg_training" / "ste").rglob("*.py"))
    names = {path.name for path in files}
    assert {"ste_job.py", "ste_dummy_job.py", "jobs.py", "state.py", "run_contract.py", "pauses.py"} <= names
    words = re.compile(r"pgrep|pkill|killall|pidof", re.IGNORECASE)
    hits = [f"{path.name}:{number}" for path in files for number, line in enumerate(path.read_text().splitlines(), 1)
            if words.search(line)]
    assert hits == []


# ================================================================================================ dead jobs (F-d)
def test_f_d_a_killed_job_reads_dead_the_waiter_says_died_and_the_same_command_resumes(bench):
    """F-d with SIGKILL of the whole job (wrapper and command) as the power cut: nothing records an exit code."""
    cmd = bench.dummy("cut", steps=30, step_s=0.03)
    assert bench.launch("cut", cmd).returncode == 0
    waiter = bench.start_wait("cut")
    wait_for(lambda: bench.step("cut") >= 6, what="some checkpoints")
    first = bench.job("cut")
    os.killpg(first["pid"], signal.SIGKILL)
    wait_for(lambda: not state.job_alive(bench.job("cut")), what="the job to be gone")

    assert waiter.wait(timeout=WAIT_S) == jobs.EXIT_DIED == 21
    died = re.fullmatch(r"L0\.7 cut DIED exit=none duration=(\d+\.\d)s effective=\d+\.\ds \(no exit code recorded; dead\)\n",
                        waiter.stdout.read())
    # the duration runs to the last sign of life (the newest file of the run folder: here the last checkpoint or log
    # line), not to the wrapper's last beat, which is a minute apart in real use. The waiter prints it rounded to 0.1 s, so
    # the upper bound allows half a display step (L07-F1, laptop 20 Nov 2026: raw 0.255 s printed "0.3" against 0.293 s elapsed)
    assert 0.1 <= float(died.group(1)) <= time.time() - first["started"] + DISPLAY_HALF_STEP_S
    assert re.search(r"^cut +L0\.7 +dead +exit=none ", bench.status(), re.M)
    assert not (bench.run_dir("cut") / "exit_code").exists()
    survived = bench.step("cut")
    assert 6 <= survived < 30

    again = bench.launch("cut", cmd)                                       # the same command
    assert again.returncode == 0, again.stderr
    second = bench.job("cut")
    assert second["launch"] == 2 and (second["pid"], second["pid_start"]) != (first["pid"], first["pid_start"])
    done = bench.wait("cut")
    assert done.returncode == 0 and " DONE exit=0 " in line_of(done)
    log = (bench.run_dir("cut") / "job.log").read_text()                   # one log, appended
    assert "fresh start" in log and f"resumed from step {survived}" in log
    assert json.loads((bench.run_dir("cut") / "result.json").read_text()) == {"steps": 30, "total": 465.0}
    rows = [json.loads(line) for line in (bench.run_dir("cut") / "launches.jsonl").read_text().splitlines()]
    assert [(row["event"], row["launch"]) for row in rows] == [("launch", 1), ("launch", 2), ("end", 2)]
    assert re.search(r"^cut +L0\.7 +dead +exit=0 \(DONE\) ", bench.status(), re.M)


# ================================================================================================ resumed runs (L07-I4)
RESUME_STEPS, RESUME_STEP_S = 40, 0.05            # 2.0 s of steps for the whole run
RESUME_KILL_AT = 32                               # the "power cut": launch 2 has only 8 steps (0.4 s) left to do


def cut_and_resume(bench: Bench, name: str, min_s: float) -> subprocess.CompletedProcess:
    """The resume drill, fast: launch, SIGKILL the whole job late in its run (DIED), relaunch with ``bash cmd.txt``,
    wait. Returns the second waiter's result."""
    cmd = bench.dummy(name, steps=RESUME_STEPS, step_s=RESUME_STEP_S, every=5)
    assert bench.launch(name, cmd, min_s=min_s).returncode == 0
    wait_for(lambda: bench.step(name) >= RESUME_KILL_AT - 2, what="most of the run")
    os.killpg(bench.job(name)["pid"], signal.SIGKILL)
    wait_for(lambda: not state.job_alive(bench.job(name)), what="the job to be gone")
    assert bench.wait(name).returncode == jobs.EXIT_DIED
    again = subprocess.run(["bash", str(bench.run_dir(name) / "cmd.txt")], env=bench.env, capture_output=True,
                           text=True, timeout=WAIT_S)
    assert again.returncode == 0 and "launch=2" in again.stdout, again.stderr
    return bench.wait(name)


def test_a_resumed_run_that_finishes_correctly_reads_done(bench):
    """L07-I4 (QC): the run needs about 2.0 s of effective time and --min-s is 1.5 s. Killed late and relaunched with
    cmd.txt (AUTOMATION section 2.3), its second launch lasts well under 1.5 s. Judged on the run's total effective
    time, as the trainer recorded it in its checkpoints, it is DONE; before the fix it read ENDED_EARLY (20)."""
    done = cut_and_resume(bench, "resumed", min_s=1.5)
    assert done.returncode == 0, done.stdout
    found = re.fullmatch(r"L0\.7 resumed DONE exit=0 duration=(\d+\.\d)s effective=(\d+\.\d)s run_effective=(\d+\.\d)s",
                         line_of(done))
    assert found, line_of(done)
    assert 1.5 <= float(found.group(3))                                        # judged on the whole run
    assert float(found.group(3)) >= RESUME_STEPS * RESUME_STEP_S - 0.1
    assert "resumed from step" in (bench.run_dir("resumed") / "job.log").read_text()


def test_a_resumed_run_that_is_too_short_in_total_is_still_flagged(bench):
    """L07-I4: the same resumed run against --min-s 5.0 s: its whole run (about 2 s) is under the minimum, so it is a
    real early end, flagged 20."""
    done = cut_and_resume(bench, "short_run", min_s=5.0)
    assert done.returncode == jobs.EXIT_ENDED_EARLY == 20, done.stdout
    assert " ENDED_EARLY exit=0 (DONE) " in line_of(done) and line_of(done).endswith("expected_min=5.0s")


def test_a_relaunch_that_saves_no_progress_is_judged_on_its_own_time(bench):
    """L07-I4: the trainer's progress counts only if this launch wrote it. A command that saves nothing (here a quick
    exit 0, launched under the same name in the same run folder after a killed trainer) cannot borrow the earlier
    launch's time: it is judged on its own effective time and flagged."""
    cmd = bench.dummy("borrow", steps=RESUME_STEPS, step_s=RESUME_STEP_S, every=5)
    assert bench.launch("borrow", cmd, min_s=1.5).returncode == 0
    wait_for(lambda: bench.step("borrow") >= RESUME_KILL_AT - 2, what="most of the run")
    os.killpg(bench.job("borrow")["pid"], signal.SIGKILL)
    wait_for(lambda: not state.job_alive(bench.job("borrow")), what="the job to be gone")
    assert bench.launch("borrow", exit_cmd(0), min_s=1.5).returncode == 0
    done = bench.wait("borrow")
    assert done.returncode == jobs.EXIT_ENDED_EARLY and "run_effective" not in line_of(done), line_of(done)


@pytest.mark.parametrize("launch, progress, verdict, status, shown", [
    (2, {"step": 40, "effective_s": 70.0, "saved": "late"}, "DONE", 0, "run_effective=70.0s"),
    (2, {"step": 40, "effective_s": 70.0, "saved": "early"}, "ENDED_EARLY", 20, None),       # saved before this launch
    (2, {"step": 40, "effective_s": 50.0, "saved": "late"}, "ENDED_EARLY", 20, "run_effective=50.0s"),
    (1, {"step": 40, "effective_s": 50.0, "saved": "late"}, "ENDED_EARLY", 20, None),        # launch-1 line unchanged
    (1, {"step": 40, "effective_s": 70.0, "saved": "late"}, "DONE", 0, None),
    (2, {"step": 40, "effective_s": float("nan"), "saved": "late"}, "ENDED_EARLY", 20, None),
    (2, [1, 2], "ENDED_EARLY", 20, None), (2, "torn{", "ENDED_EARLY", 20, None),
], ids=["resumed_done", "stale_note", "resumed_too_short", "fresh_too_short", "fresh_done", "nan", "list", "torn"])
def test_the_waiter_judges_the_whole_run_from_the_trainers_note(bench, monkeypatch, launch, progress, verdict, status,
                                                                shown):
    """L07-I4, in process, no timing: this launch ran 30 s of a run that needs 60 s (--min-s). The trainer's note
    (progress.json) decides only if it was saved during this launch; an unusable note never changes the waiter's own
    status (never 23)."""
    run = bench.run_dir("noted")
    run.mkdir(parents=True)
    now = time.time()
    job = {"task": "L0.7", "pid": 2 ** 22 + 1, "pid_start": 1, "boot_id": state.boot_id(), "cmd": ["x"], "cwd": "/",
           "run_dir": str(run), "log": str(run / "job.log"), "started": now - 30.0, "expected_min_s": 60.0,
           "gpu_h": 0.0, "launch": launch, "child_pid": 2 ** 22 + 3, "child_start": 3, "exit_code": 0, "ended": now}
    (run / "exit_code").write_text("0\n")
    if isinstance(progress, dict):
        progress = dict(progress, saved=now - (40.0 if progress["saved"] == "early" else 1.0))
        (run / rc.PROGRESS_NAME).write_text(json.dumps(progress))
    else:
        (run / rc.PROGRESS_NAME).write_text(progress if isinstance(progress, str) else json.dumps(progress))
    monkeypatch.setattr(state, "read", lambda: {"jobs": {"noted": job}})
    outcome = jobs.wait("noted", poll_s=0.01)
    assert (outcome.verdict, outcome.status) == (verdict, status), outcome.line
    if shown is None:
        assert "run_effective" not in outcome.line
    else:
        assert f" {shown}" in outcome.line


def previous_boot_job(bench: Bench, name: str, sleeper: subprocess.Popen) -> None:
    """Write the record a power cut leaves: a job launched in another boot, whose pid number is alive again now."""
    run = bench.run_dir(name)
    run.mkdir(parents=True)
    record = {"task": "L0.7", "pid": sleeper.pid, "pid_start": state.process_start_time(sleeper.pid),
              "boot_id": OTHER_BOOT, "cmd": bench.dummy(name), "cwd": str(ROOT), "run_dir": str(run),
              "log": str(run / "job.log"), "started": time.time() - 500.0, "expected_min_s": 0.0, "gpu_h": 0.0,
              "launch": 1, "child_pid": None, "child_start": None, "exit_code": None, "ended": None}
    (run / "job.json").write_text(json.dumps(dict(record, name=name, beat_s=60.0)))
    state.update(lambda data: data["jobs"].update({name: record}))


def test_f_d_a_record_from_a_previous_boot_is_dead_never_alive(bench):
    """F-d. The stale record's pid exists (another program has the number after the reboot) and even its start time
    matches; a pid-only check would wait on it for ever. The boot id settles it."""
    sleeper = subprocess.Popen([sys.executable, "-c", "import time\nwhile True: time.sleep(0.05)"])
    try:
        previous_boot_job(bench, "stale", sleeper)
        assert re.search(r"^stale +L0\.7 +dead \(previous boot\) +exit=none ", bench.status(), re.M)
        done = bench.wait("stale")                                         # returns at once: it does not watch the pid
        assert done.returncode == jobs.EXIT_DIED
        assert line_of(done).startswith("L0.7 stale DIED exit=none ")
        assert line_of(done).endswith("(no exit code recorded; dead (previous boot))")
        assert sleeper.poll() is None                                      # the stranger with that pid was not touched

        again = bench.launch("stale", bench.dummy("stale"))                # the same command relaunches: not refused
        assert again.returncode == 0, again.stderr
        assert bench.job("stale")["boot_id"] == state.boot_id() and bench.job("stale")["launch"] == 2
        assert bench.wait("stale").returncode == 0
    finally:
        reap(sleeper)


def test_a_job_that_ended_before_the_reboot_keeps_its_real_exit_code(bench):
    sleeper = subprocess.Popen([sys.executable, "-c", "import time\nwhile True: time.sleep(0.05)"])
    try:
        previous_boot_job(bench, "finished", sleeper)
        (bench.run_dir("finished") / "exit_code").write_text("3\n")
        done = bench.wait("finished")
        assert done.returncode == rc.EXIT_CAP and " CAP exit=3 " in line_of(done)
        assert re.search(r"^finished +L0\.7 +dead \(previous boot\) +exit=3 \(CAP\) ", bench.status(), re.M)
    finally:
        reap(sleeper)


def test_a_command_killed_alone_is_recorded_with_its_signal(bench):
    """Only the command gets SIGKILL; the wrapper lives and records 128 + 9, as a shell would."""
    assert bench.launch("shot", bench.dummy("shot", steps=100_000)).returncode == 0
    os.kill(bench.child("shot"), signal.SIGKILL)
    done = bench.wait("shot")
    assert done.returncode == 137 and " FAILED exit=137 " in line_of(done)
    rows = [json.loads(line) for line in (bench.run_dir("shot") / "launches.jsonl").read_text().splitlines()]
    assert rows[-1]["event"] == "end" and rows[-1]["signal"] == "SIGKILL"


def test_the_wrapper_killed_alone_leaves_a_live_job_that_cannot_be_relaunched(bench):
    """The command still runs but nothing will record its exit code. It is not dead: a relaunch now would put two
    trainers in one run folder."""
    cmd = bench.dummy("orphan", steps=100_000)
    assert bench.launch("orphan", cmd).returncode == 0
    child = bench.child("orphan")
    os.kill(bench.job("orphan")["pid"], signal.SIGKILL)
    wait_for(lambda: state.job_status(bench.job("orphan")) == state.ALIVE_NO_WRAPPER, what="the wrapper to be gone")
    assert re.search(r"^orphan +L0\.7 +alive \(wrapper gone\) +exit=none ", bench.status(), re.M)
    refused = bench.launch("orphan", cmd)
    assert refused.returncode == rc.EXIT_REFUSED and "alive" in refused.stderr
    waiter = bench.start_wait("orphan")
    seen = bench.step("orphan")
    wait_for(lambda: bench.step("orphan") >= seen + 4, what="the command to go on")
    assert waiter.poll() is None                                           # still waiting: the command lives
    os.kill(child, signal.SIGKILL)
    assert waiter.wait(timeout=WAIT_S) == jobs.EXIT_DIED
    assert " DIED exit=none " in waiter.stdout.read()


# ================================================================================================ refusals
def test_a_live_job_is_not_launched_twice(bench):
    cmd = bench.dummy("once", steps=100_000)
    assert bench.launch("once", cmd).returncode == 0
    first = bench.job("once")
    refused = bench.launch("once", cmd)
    assert refused.returncode == rc.EXIT_REFUSED == 2 and "once" in refused.stderr and "alive" in refused.stderr
    other_name = run_py([TOOL, "launch", "--task", "L0.7", "--name", "twice", "--run-dir", bench.run_dir("once"), "--min-s", 0,
                         "--gpu-h", 0, "--", *cmd], bench.env)
    assert other_name.returncode == rc.EXIT_REFUSED and "run folder" in other_name.stderr
    assert bench.job("once") == dict(first, child_pid=bench.child("once"), child_start=bench.job("once")["child_start"])
    assert "twice" not in state.read()["jobs"] and state.job_alive(bench.job("once"))


def test_launch_refuses_what_the_budget_does_not_allow(bench, tmp_path):
    """Task L0.7 has no GPU-hours in configs/ste_learning.toml: a job that asks for some is not started."""
    refused = bench.launch("greedy", bench.dummy("greedy"), gpu_h=0.5)
    assert refused.returncode == rc.EXIT_REFUSED
    assert "task L0.7" in refused.stderr and "cap 0.0 GPU-h" in refused.stderr and "asked 0.5" in refused.stderr
    assert "greedy" not in state.read()["jobs"] and not bench.run_dir("greedy").exists()
    unknown = bench.launch("nowhere", bench.dummy("nowhere"), task="L0.99")
    assert unknown.returncode == rc.EXIT_REFUSED and "L0.99" in unknown.stderr
    path = settings(tmp_path, 19.0, L0_11=3.0)
    budget.log_interval("L0.11", "earlier", "cuda", time.time() - 3 * 3600.0, time.time() - 1.0)       # 3 h already used
    full = bench.launch("sweep", bench.dummy("sweep"), gpu_h=0.5, task="L0.11", extra=("--settings", path))
    assert full.returncode == rc.EXIT_REFUSED and "used 3.000" in full.stderr and "sweep" not in state.read()["jobs"]


def test_bad_arguments_and_unknown_jobs(bench):
    assert run_py([TOOL, "launch", "--task", "L0.7", "--name", "x", "--run-dir", bench.run_dir("x"), "--min-s", 0, "--gpu-h", 0],
                  bench.env).returncode == rc.EXIT_REFUSED                # no command
    assert bench.launch("bad name", exit_cmd(0)).returncode == rc.EXIT_REFUSED
    assert bench.launch("neg", exit_cmd(0), min_s=-1.0).returncode == rc.EXIT_REFUSED
    assert run_py([TOOL, "launch", "--name", "x", "--run-dir", bench.run_dir("x"), "--", "true"], bench.env).returncode == 2
    assert state.read()["jobs"] == {}
    unknown = bench.wait("never_launched")
    assert unknown.returncode == jobs.EXIT_NO_SUCH_JOB == 22 and unknown.stdout == "" and "never_launched" in unknown.stderr
    assert bench.status() == "no job has been launched\n"


def test_a_command_that_cannot_be_started_is_recorded_not_lost(bench):
    """A misspelt program: the wrapper cannot start it. That is an exit code (127, as a shell says "not found"), not a
    job that died without a trace."""
    assert bench.launch("typo", [f"/no/such/program_{uuid.uuid4().hex}", "--flag"]).returncode == 0
    done = bench.wait("typo")
    assert done.returncode == jobs.EXIT_NOT_STARTED == 127 and " FAILED exit=127 " in line_of(done)
    assert "could not be started" in (bench.run_dir("typo") / "job.log").read_text()
    assert bench.job("typo")["exit_code"] == 127 and bench.job("typo")["child_pid"] is None


def test_the_waiters_own_failure_never_looks_like_a_jobs_exit_code(bench):
    """A state file the waiter cannot read: its own status (23) and nothing on stdout, not a traceback's status 1,
    which a job could have returned too."""
    assert bench.launch("fine", exit_cmd(0)).returncode == 0
    assert bench.wait("fine").returncode == 0
    shared.state_file().write_text("{not json")
    broken = bench.wait("fine")
    assert broken.returncode == jobs.EXIT_TOOL_ERROR == 23 and broken.stdout == "" and "not valid JSON" in broken.stderr
    assert run_py([TOOL, "status"], bench.env).returncode == jobs.EXIT_TOOL_ERROR
    assert run_py([TOOL, "wait", "fine", "--poll-s", "0"], bench.env).returncode == rc.EXIT_REFUSED
    shared.state_file().unlink()


def test_a_wrapper_started_by_hand_runs_nothing(bench):
    """``_run`` is the launcher's: a wrapper that the run folder's record does not name (another pid) starts no
    command and writes no exit code."""
    assert bench.launch("mine", exit_cmd(0)).returncode == 0
    assert bench.wait("mine").returncode == 0
    run = bench.run_dir("mine")
    before = {path.name: path.read_bytes() for path in run.iterdir()}
    by_hand = run_py([TOOL, "_run", run], bench.env)
    assert by_hand.returncode == rc.EXIT_REFUSED and "does not record this wrapper" in by_hand.stdout
    assert {path.name: path.read_bytes() for path in run.iterdir()} == before
    empty = run_py([TOOL, "_run", bench.tmp / "no_such_run"], bench.env)
    assert empty.returncode == rc.EXIT_REFUSED


# ================================================================================================ GPU-hours and pauses
def test_a_gpu_job_logs_its_hours_beat_by_beat_and_at_its_end(bench, tmp_path):
    path = settings(tmp_path, 19.0, L0_11=3.0)
    launched = bench.launch("sweep", bench.dummy("sweep", steps=20, step_s=0.03), gpu_h=0.5, task="L0.11",
                            extra=("--settings", path, "--beat-s", 0.1))
    assert launched.returncode == 0, launched.stderr
    wait_for(lambda: shared.gpu_hours_log().exists() and budget.task_gpu_h("L0.11") > 0.0, what="the first beat")
    assert state.job_alive(bench.job("sweep"))                             # counted while it still runs
    assert bench.wait("sweep").returncode == 0
    job = bench.job("sweep")
    rows = [json.loads(line) for line in shared.gpu_hours_log().read_text().splitlines()]
    assert len(rows) >= 3 and {(row["group"], row["job"], row["device"]) for row in rows} == {("L0.11", "sweep", "cuda")}
    assert all(row["pids"] == [job["child_pid"]] for row in rows)          # L07-C1: whose time it was
    assert all(row["run_dir"] == job["run_dir"] for row in rows)            # L07-I1: which run it was
    assert all(later["start"] == earlier["end"] for earlier, later in zip(rows, rows[1:]))      # one unbroken interval
    assert job["started"] <= rows[0]["start"] and rows[-1]["end"] == pytest.approx(job["ended"], abs=0.5)
    used_s = budget.task_gpu_h("L0.11") * 3600.0
    assert used_s == pytest.approx(rows[-1]["end"] - rows[0]["start"]) and 0.5 <= used_s <= job["ended"] - job["started"]
    assert budget.phase_gpu_h("L0") == budget.task_gpu_h("L0.11") and budget.task_gpu_h("L0.7") == 0.0


def test_f_d_a_gpu_job_that_asked_for_its_whole_cap_resumes_with_the_same_line(bench, tmp_path):
    """F-d for the real jobs: L0.11 may use 3 GPU-h and its job asks for all 3. Killed after some GPU time, the SAME
    launch line must start it again: the hours it already logged are its own, not a second request."""
    path = settings(tmp_path, 19.0, L0_11=3.0)
    cmd = bench.dummy("sweep", steps=30, step_s=0.03)
    extra = ("--settings", path, "--beat-s", 0.05)
    assert bench.launch("sweep", cmd, gpu_h=3.0, task="L0.11", extra=extra).returncode == 0
    wait_for(lambda: bench.step("sweep") >= 6 and budget.job_gpu_h("L0.11", "sweep") > 0.0, what="logged GPU time")
    os.killpg(bench.job("sweep")["pid"], signal.SIGKILL)
    wait_for(lambda: not state.job_alive(bench.job("sweep")), what="the job to be gone")
    used = budget.task_gpu_h("L0.11")
    assert used > 0.0
    again = bench.launch("sweep", cmd, gpu_h=3.0, task="L0.11", extra=extra)          # the same line
    assert again.returncode == 0, again.stderr
    other = bench.launch("second", bench.dummy("second"), gpu_h=3.0, task="L0.11", extra=extra)
    assert other.returncode == rc.EXIT_REFUSED and "asked 3.0" in other.stderr       # a new job cannot have 3 more
    done = bench.wait("sweep")
    assert done.returncode == 0 and " DONE exit=0 " in line_of(done)
    assert "resumed from step" in (bench.run_dir("sweep") / "job.log").read_text()
    assert budget.job_gpu_h("L0.11", "sweep") == budget.task_gpu_h("L0.11") > used


def test_qc_reproduction_a_new_run_under_a_finished_jobs_name_is_charged_in_full(bench, tmp_path):
    """L07-I1 end to end: job "sweep" ran in one run folder and finished, asking the task's whole 3 GPU-h. A new run
    folder under the same name asking 3 again must be refused (it would take the task past its cap); the same line
    in the old run folder still resumes."""
    path = settings(tmp_path, 19.0, L0_11=3.0)
    extra = ("--settings", path, "--beat-s", 0.05)
    first = bench.launch("sweep", bench.dummy("sweep", steps=10), gpu_h=3.0, task="L0.11", extra=extra)
    assert first.returncode == 0, first.stderr
    assert bench.wait("sweep").returncode == 0 and budget.task_gpu_h("L0.11") > 0.0
    other_run = bench.tmp / "runs" / "sweep_rerun"
    rerun = run_py([TOOL, "launch", "--task", "L0.11", "--name", "sweep", "--run-dir", other_run, "--min-s", 0.0,
                    "--gpu-h", 3.0, *extra, "--", *bench.dummy("sweep")], bench.env)
    assert rerun.returncode == rc.EXIT_REFUSED and "asked 3.0" in rerun.stderr, rerun.stdout
    assert not other_run.exists()
    again = bench.launch("sweep", bench.dummy("sweep", steps=10), gpu_h=3.0, task="L0.11", extra=extra)  # same line
    assert again.returncode == 0, again.stderr
    assert bench.wait("sweep").returncode == 0


def test_an_owner_pause_stops_the_command_not_the_wrapper_and_is_not_counted(bench, tmp_path):
    """F-e end to end with the real scripts/gpu_pause.sh and its DEFAULT exclusion: the pattern (the test's own
    folder name) is on the command line of the command AND of the wrapper; only the command is stopped. ``status``
    says paused, and the waiter's effective duration leaves the pause out."""
    pattern = tmp_path.name
    assert bench.launch("held", bench.dummy("held", steps=30, step_s=0.03)).returncode == 0
    job, child = bench.job("held"), bench.child("held")
    assert pattern in Path(f"/proc/{job['pid']}/cmdline").read_text() and pattern in Path(f"/proc/{child}/cmdline").read_text()
    wait_for(lambda: bench.step("held") >= 4, what="some progress")
    pause_script("pause", tmp_path, bench.shared, pattern)
    wait_for(lambda: proc_state(child) == "T", what="the command to be stopped")
    assert proc_state(job["pid"]) != "T"
    assert re.search(r"^held +L0\.7 +alive \(paused\) +exit=none ", bench.status(), re.M)
    held_at = bench.step("held")
    time.sleep(1.2)                                                        # the pause itself: a fixed wait is the point
    assert bench.step("held") == held_at
    pause_script("resume", tmp_path, bench.shared, pattern)
    done = bench.wait("held")
    assert done.returncode == 0, done.stderr
    found = re.fullmatch(r"L0\.7 held DONE exit=0 duration=(\d+\.\d)s effective=(\d+\.\d)s", line_of(done))
    duration_s, effective_s = float(found.group(1)), float(found.group(2))
    paused_s = sum(end - start for start, end in pauses.paused_intervals())
    assert paused_s >= 1.2 and duration_s - effective_s == pytest.approx(paused_s, abs=0.11)
    events = [json.loads(line) for line in shared.pauses_log().read_text().splitlines()]
    assert [event["event"] for event in events] == ["pause", "resume"] and events[0]["pids"] == [child]


def pause_line(event: str, time_s: float, pids: list | None) -> None:
    """One gpu_pause.sh line in the bench's shared pause log; ``pids=None`` leaves the key out (legacy line)."""
    row = {"event": event, "time": time_s, "by": "owner"}
    if pids is not None:
        row["pids"] = pids
    log = shared.pauses_log()
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as stream:
        stream.write(json.dumps(row) + "\n")


def test_launch_is_refused_while_an_owner_pause_is_open(bench, tmp_path):
    """L07-C1 (a): a pause is also the owner's "I am using this PC", even one that stopped no job. A job launched
    during it would run on the GPU unpaused. The launch is refused (exit 2), nothing is started, nothing is written."""
    pause_line("pause", time.time() - 30.0, [])
    refused = bench.launch("late", bench.dummy("late"))
    assert refused.returncode == rc.EXIT_REFUSED and refused.stdout == ""
    assert len(refused.stderr.splitlines()) == 1, refused.stderr
    assert "pause" in refused.stderr and "by owner" in refused.stderr and "gpu_pause.sh resume" in refused.stderr
    assert "nothing was launched" in refused.stderr
    assert not bench.run_dir("late").exists() and not (bench.shared / "state.json").exists()
    pause_line("resume", time.time(), [])                                  # the owner's resume: the launch goes ahead
    assert bench.launch("late", bench.dummy("late")).returncode == 0
    assert bench.wait("late").returncode == 0


@pytest.mark.parametrize("bys, refused", [
    (["lead"], False), (["owner"], True), (["lead", "owner"], True), (["owner", "lead"], True), ([None], True),
], ids=["session_pause", "owner_pause", "session_then_owner", "owner_then_session", "untagged_legacy"])
def test_launch_goes_ahead_only_under_the_sessions_own_pause(bench, bys, refused):
    """L07-C1b: the lead pauses only its own siblings (GPU_PAUSE_BY=lead) to run a solo job (AUTOMATION 2.2). Such a
    pause does not block a launch; any owner pause still does, alone or mixed, and so does an untagged line."""
    for offset, by in enumerate(bys):
        row = {"event": "pause", "time": time.time() - 30.0 + offset, "pids": [4242]}
        if by is not None:
            row["by"] = by
        log = shared.pauses_log()
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as stream:
            stream.write(json.dumps(row) + "\n")
    done = bench.launch("solo", bench.dummy("solo", steps=4))
    if refused:
        assert done.returncode == rc.EXIT_REFUSED and "gpu_pause.sh resume" in done.stderr, done.stdout
        assert len(done.stderr.splitlines()) == 1 and not bench.run_dir("solo").exists()
    else:
        assert done.returncode == 0, done.stderr
        assert bench.wait("solo").returncode == 0


def test_owner_pauses_lists_the_open_owner_pauses_for_gpu_pause_sh(bench):
    """L07-C1c: the check gpu_pause.sh runs before the lead's resume or stop. Exit 0 and one line when none is open;
    exit 2 and one line per owner pause otherwise; the lead's own pause is not listed."""
    done = run_py([TOOL, "owner-pauses"], bench.env)
    assert done.returncode == 0 and done.stdout.strip() == "no owner pause is open"
    log = shared.pauses_log()
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as stream:
        for offset, by in enumerate(("lead", "owner", "owner")):
            stream.write(json.dumps({"event": "pause", "time": time.time() - 10.0 + offset, "pids": [], "by": by}) + "\n")
    done = run_py([TOOL, "owner-pauses"], bench.env)
    assert done.returncode == rc.EXIT_REFUSED and len(done.stdout.splitlines()) == 2
    assert all("(by owner" in line for line in done.stdout.splitlines())


def test_a_pause_left_open_by_a_previous_boot_does_not_refuse_a_launch(bench):
    """After a power cut the relaunch from cmd.txt must go ahead: nothing is paused after a boot (ste/pauses.py)."""
    pause_line("pause", 1000.0, [4242])                                    # 1970: long before this boot
    launched = bench.launch("after_boot", bench.dummy("after_boot"))
    assert launched.returncode == 0, launched.stderr
    assert bench.wait("after_boot").returncode == 0


def test_qc_reproduction_a_pause_that_stopped_nothing_leaves_cap_and_hours_running(bench, tmp_path):
    """L07-C1 (b) end to end. A GPU job runs; the owner then pauses with a copy that found nothing to stop (``pids:
    []``) and does not resume. The job was never stopped, so its 1 s cap must fire and its GPU time must be logged.
    Before the fix the open pause froze its clock (it ran all its steps, DONE) and its hours read 0."""
    path = settings(tmp_path, 19.0, L0_11=3.0)
    cmd = bench.dummy("unpaused", steps=200, step_s=0.03, cap_s=1.0)
    assert bench.launch("unpaused", cmd, gpu_h=0.5, task="L0.11", extra=("--settings", path, "--beat-s", 0.1)).returncode == 0
    wait_for(lambda: bench.step("unpaused") >= 2, what="the first checkpoint")
    pause_line("pause", time.time(), [])
    done = bench.wait("unpaused")
    assert done.returncode == rc.EXIT_CAP and " CAP exit=3 " in line_of(done), done.stdout
    assert bench.step("unpaused") < 200                                    # stopped at the cap, not at the end
    assert budget.task_gpu_h("L0.11") * 3600.0 >= 1.0


@pytest.mark.parametrize("pids, effective_s", [([], 90.0), ([2 ** 22 + 9], 90.0), ([2 ** 22 + 3], 60.0),
                                               ([2 ** 22 + 9, 2 ** 22 + 3], 60.0), (None, 60.0)],
                         ids=["stopped_nothing", "stopped_another", "stopped_its_command", "stopped_both", "legacy"])
def test_the_waiter_takes_off_only_a_pause_that_stopped_the_jobs_command(bench, monkeypatch, pids, effective_s):
    """L07-C1 (b) and (c) for the waiter: a job ran 90 s with a 30 s pause inside. The pause counts only if it lists
    the job's command (the wrapper is never paused); a line without pids counts, as before (legacy rule)."""
    run = bench.run_dir("judged")
    run.mkdir(parents=True)
    now = time.time()
    job = {"task": "L0.7", "pid": 2 ** 22 + 1, "pid_start": 1, "boot_id": state.boot_id(), "cmd": ["x"], "cwd": "/",
           "run_dir": str(run), "log": str(run / "job.log"), "started": now - 100.0, "expected_min_s": 0.0,
           "gpu_h": 0.0, "launch": 1, "child_pid": 2 ** 22 + 3, "child_start": 3, "exit_code": 0, "ended": now - 10.0}
    (run / "exit_code").write_text("0\n")                                  # no such pids exist: the job is over
    pause_line("pause", now - 80.0, pids)
    pause_line("resume", now - 50.0, [] if pids is None else pids)
    monkeypatch.setattr(state, "read", lambda: {"jobs": {"judged": job}})
    outcome = jobs.wait("judged", poll_s=0.01)
    assert outcome.duration_s == pytest.approx(90.0) and outcome.effective_s == pytest.approx(effective_s)


def test_the_owners_stop_interrupts_the_command_and_the_wrapper_records_it(bench, tmp_path):
    """``gpu_pause.sh stop`` sends SIGINT to the command only; the wrapper must survive to write the exit code."""
    assert bench.launch("stopped", bench.dummy("stopped", steps=100_000)).returncode == 0
    wait_for(lambda: bench.step("stopped") >= 4, what="some progress")
    pause_script("stop", tmp_path, bench.shared, tmp_path.name)
    done = bench.wait("stopped")
    assert done.returncode == rc.EXIT_INTERRUPTED and " INTERRUPTED exit=4 " in line_of(done)


# ================================================================================================ the wrapper's own faults (L07-I3)
# The wrapper runs IN this test process (it checks that job.json records its own pid), with faults injected by
# monkeypatching: no disk is filled and no system clock is changed. The test's own folder is the shared folder, and no
# Bench is used: its clean-up kills the process group of every recorded live pid, which here would be pytest's own.
FAULT_BEAT_S = 0.05
SHORT_CMD_S = 0.6


@pytest.fixture()
def in_process(tmp_path, monkeypatch):
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")
    saved = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}

    def make(name: str = "faulty", gpu_h: float = 0.5, end_marker: bool = False) -> Path:
        """A recorded job whose command sleeps SHORT_CMD_S; ``end_marker``: it then writes ``ended.marker`` in the run
        folder, just before it exits."""
        run = tmp_path / "runs" / name
        run.mkdir(parents=True)
        me = os.getpid()
        code = f"import time\ntime.sleep({SHORT_CMD_S})\n"
        if end_marker:
            code += f"open({str(run / 'ended.marker')!r}, 'w').close()\n"
        record = {"task": "L0.11", "pid": me, "pid_start": jobs._start_ticks(me), "boot_id": state.boot_id(),
                  "cmd": [child_python(), "-c", code], "cwd": str(ROOT),
                  "run_dir": str(run), "log": str(run / "job.log"), "started": time.time(), "expected_min_s": 0.0,
                  "gpu_h": gpu_h, "launch": 1, "child_pid": None, "child_start": None, "exit_code": None, "ended": None}
        state.update(lambda data: data["jobs"].__setitem__(name, dict(record)))
        (run / "job.json").write_text(json.dumps(dict(record, name=name, beat_s=FAULT_BEAT_S, settings="unused",
                                                      env={}, shared_dir=str(tmp_path / "shared"))))
        return run

    yield make
    for number, handler in saved.items():                                   # the wrapper sets its own handlers
        signal.signal(number, handler)


def ledger_rows() -> list[dict]:
    return [json.loads(line) for line in shared.gpu_hours_log().read_text().splitlines()]


def assert_unbroken(rows: list[dict]) -> None:
    """GPU time with no negative, no overlapping and no missing piece: each line starts where the last one ended."""
    assert rows and all(row["end"] > row["start"] for row in rows)
    assert all(later["start"] == earlier["end"] for earlier, later in zip(rows, rows[1:]))


def ended_cleanly(run: Path, name: str = "faulty") -> dict:
    """The command's exit code 0 is recorded in the run folder and in state.json; returns the state record."""
    assert (run / "exit_code").read_text() == "0\n"
    job = state.read()["jobs"][name]
    assert job["exit_code"] == 0 and job["child_pid"] is not None and job["ended"] >= job["started"]
    return job


@pytest.mark.parametrize("step_s", [30.0, 0.15], ids=["longer_than_the_job", "caught_up_while_it_runs"])
def test_a_backward_clock_step_neither_ends_the_wrapper_nor_counts_negative_time(in_process, monkeypatch, step_s):
    """L07-I3 (QC): the wall clock steps back while the command runs (an NTP step). Before the fix the next beat
    raised ValueError (an interval ending before it starts), the wrapper left, the command ran on unlogged and its
    clean end read DIED. A short step is caught up while the command still runs: logging then goes on."""
    run = in_process()
    calls = []

    def stepped() -> float:
        calls.append(None)
        return time.time() - (step_s if len(calls) > 3 else 0.0)

    monkeypatch.setattr(jobs, "time", type("Clock", (), {"time": staticmethod(stepped), "sleep": staticmethod(time.sleep)}))
    assert jobs.run_wrapper(run) == rc.EXIT_DONE
    job = ended_cleanly(run)
    rows = ledger_rows()
    assert_unbroken(rows)
    assert rows[-1]["end"] == pytest.approx(job["ended"])
    if step_s < SHORT_CMD_S:                                                # logged up to the command's real end
        assert job["ended"] - rows[0]["start"] >= SHORT_CMD_S - step_s - FAULT_BEAT_S


def test_a_failed_ledger_write_is_retried_at_the_next_beat_and_flagged(in_process, monkeypatch):
    """L07-I3: any error from the ledger write (here injected twice) must not end the wrapper. The next beat logs from
    the last logged time, so the ledger has no gap; job.json counts the faults, for the waiter and the status."""
    run = in_process()
    real, calls = budget.log_interval, []

    def flaky(*args, **kwargs):
        calls.append(None)
        if len(calls) in (2, 3):
            raise RuntimeError("injected ledger fault")
        return real(*args, **kwargs)

    monkeypatch.setattr(budget, "log_interval", flaky)
    assert jobs.run_wrapper(run) == rc.EXIT_DONE
    job = ended_cleanly(run)
    rows = ledger_rows()
    assert_unbroken(rows)
    assert rows[-1]["end"] == pytest.approx(job["ended"])
    record = json.loads((run / "job.json").read_text())
    assert record["faults"] == 2 and "injected ledger fault" in record["last_fault"]


@pytest.mark.parametrize("error", [OSError(28, "No space left on device (injected)"), RuntimeError("injected")],
                         ids=["full_disk", "any_error"])
def test_a_failing_state_json_write_does_not_end_the_wrapper(in_process, monkeypatch, error):
    """L07-I3 (QC): ``state.update`` fails for its first three calls, the first being the command's pid: a full disk,
    or any other error. Before the fix that ended the wrapper at once. The pid and the exit code reach state.json
    later."""
    run = in_process()
    real, calls = state.update, []

    def full(change):
        calls.append(None)
        if len(calls) <= 3:
            raise error
        return real(change)

    monkeypatch.setattr(state, "update", full)
    assert jobs.run_wrapper(run) == rc.EXIT_DONE
    ended_cleanly(run)
    assert_unbroken(ledger_rows())
    assert json.loads((run / "job.json").read_text())["faults"] >= 1


def test_the_last_ledger_line_is_retried_after_the_command_ends(in_process, monkeypatch):
    """L07-I3: the ledger cannot be written when the command ends (its last beats and the end). The wrapper retries the
    missing line, one beat apart, with the exit code: the GPU time reaches the command's end."""
    run = in_process(name="late", end_marker=True)
    marker = run / "ended.marker"
    real, failed = budget.log_interval, []

    def full(*args, **kwargs):
        if marker.exists() and len(failed) < 2:
            failed.append(None)
            raise OSError(28, "No space left on device (injected)")
        return real(*args, **kwargs)

    monkeypatch.setattr(budget, "log_interval", full)
    assert jobs.run_wrapper(run) == rc.EXIT_DONE
    assert len(failed) == 2
    job = ended_cleanly(run, "late")
    rows = ledger_rows()
    assert_unbroken(rows)
    assert rows[-1]["end"] == pytest.approx(job["ended"])
    assert json.loads((run / "job.json").read_text())["faults"] >= 2


def test_the_exit_code_is_written_even_if_the_disk_is_full_when_the_command_ends(in_process, monkeypatch):
    """L07-I3: the exit_code file cannot be written twice when the command ends; the wrapper retries, one beat apart,
    instead of leaving with the code unrecorded (the waiter would read DIED)."""
    run = in_process(gpu_h=0.0)
    real, failed = jobs.atomic.write_text, []

    def full(path, text):
        if Path(path).name == jobs.EXIT_FILE and len(failed) < 2:
            failed.append(path)
            raise OSError(28, "No space left on device (injected)")
        return real(path, text)

    monkeypatch.setattr(jobs.atomic, "write_text", full)
    assert jobs.run_wrapper(run) == rc.EXIT_DONE
    assert len(failed) == 2
    ended_cleanly(run)
    assert json.loads((run / "job.json").read_text())["faults"] >= 2


def test_the_waiter_and_the_status_show_the_wrappers_faults(tmp_path, monkeypatch):
    """L07-I3: a job whose wrapper had to retry a write ended DONE, and both the waiter's line and the status say how
    many writes failed (the details are in job.json and job.log)."""
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")
    run = tmp_path / "runs" / "noted"
    run.mkdir(parents=True)
    now = time.time()
    job = {"task": "L0.7", "pid": 2 ** 22 + 1, "pid_start": 1, "boot_id": state.boot_id(), "cmd": ["x"], "cwd": "/",
           "run_dir": str(run), "log": str(run / "job.log"), "started": now - 10.0, "expected_min_s": 0.0,
           "gpu_h": 0.0, "launch": 1, "child_pid": 2 ** 22 + 3, "child_start": 3, "exit_code": 0, "ended": now}
    (run / "exit_code").write_text("0\n")
    (run / "job.json").write_text(json.dumps(dict(job, name="noted", faults=2, last_fault="ledger: injected")))
    monkeypatch.setattr(state, "read", lambda: {"jobs": {"noted": job}})
    outcome = jobs.wait("noted", poll_s=0.01)
    assert outcome.verdict == "DONE" and outcome.status == 0 and " faults=2 " in outcome.line + " "
    assert "faults=2" in jobs.status_lines()[0]
    (run / "job.json").write_text(json.dumps(dict(job, name="noted", faults="two")))         # a malformed note
    outcome = jobs.wait("noted", poll_s=0.01)
    assert (outcome.verdict, outcome.status) == ("DONE", 0) and "faults" not in outcome.line
    (run / "job.json").write_text("[1, 2]")
    assert jobs.wait("noted", poll_s=0.01).status == 0 and "faults" not in jobs.status_lines()[0]


# ================================================================================================ in process
@pytest.mark.parametrize("exit_code, effective_s, min_s, verdict, status", [
    (0, 100.0, 60.0, "DONE", 0), (0, 60.0, 60.0, "DONE", 0), (0, 59.9, 60.0, "ENDED_EARLY", 20),
    (3, 100.0, 60.0, "CAP", 3), (4, 100.0, 60.0, "INTERRUPTED", 4), (5, 100.0, 60.0, "NONFINITE", 5),
    (6, 100.0, 60.0, "CONTROL_FAILED", 6), (6, 1.0, 60.0, "ENDED_EARLY", 6),
    (2, 100.0, 60.0, "REFUSED", 2), (1, 100.0, 60.0, "FAILED", 1), (137, 100.0, 60.0, "FAILED", 137),
    (1, 3.0, 60.0, "ENDED_EARLY", 1), (2, 0.1, 60.0, "ENDED_EARLY", 2), (20, 100.0, 0.0, "FAILED", 20),
    (None, 100.0, 60.0, "DIED", 21), (None, 1.0, 60.0, "DIED", 21),
])
def test_verdict_table(exit_code, effective_s, min_s, verdict, status):
    assert jobs.verdict(exit_code, effective_s, min_s) == (verdict, status)


def test_a_relaunch_under_the_waiter_does_not_mix_up_the_two_launches(bench, monkeypatch):
    """The waiter watches launch 1; before it looks again the job has ended (exit 3) and been relaunched. It reports
    launch 1 from ``exit_code.1``, not the new launch's state."""
    run = bench.run_dir("twice")
    run.mkdir(parents=True)
    first = {"task": "L0.7", "pid": 2 ** 22 + 1, "pid_start": 1, "boot_id": state.boot_id(), "cmd": ["x"], "cwd": "/",
             "run_dir": str(run), "log": str(run / "job.log"), "started": time.time() - 50.0, "expected_min_s": 0.0,
             "gpu_h": 0.0, "launch": 1, "child_pid": None, "child_start": None, "exit_code": None, "ended": None}
    second = dict(first, pid=2 ** 22 + 2, pid_start=2, launch=2, started=time.time())       # no such pids exist
    (run / "exit_code.1").write_text("3\n")
    reads = iter([{"jobs": {"twice": first}}])
    monkeypatch.setattr(state, "read", lambda: next(reads, {"jobs": {"twice": second}}))
    outcome = jobs.wait("twice", poll_s=0.01)
    assert (outcome.verdict, outcome.exit_code, outcome.status) == ("CAP", 3, 3)
    assert outcome.line.startswith("L0.7 twice CAP exit=3 ")


def test_the_waiters_own_codes_collide_with_no_job_code():
    own = {jobs.EXIT_ENDED_EARLY, jobs.EXIT_DIED, jobs.EXIT_NO_SUCH_JOB, jobs.EXIT_TOOL_ERROR}
    assert own == {20, 21, 22, 23} and not own & set(rc.EXIT_NAMES)


def test_importing_loads_no_pytorch_and_the_scripts_compile():
    code = "import sys\nimport svg_training.ste.jobs\nassert 'torch' not in sys.modules and 'numpy' not in sys.modules\n"
    done = subprocess.run([child_python(), "-c", code], env=child_env(str(SOURCE)), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    for script in (TOOL, DUMMY):
        helped = run_py([script, "--help"], child_env(str(SOURCE)))
        assert helped.returncode == 0 and "usage" in helped.stdout
    assert "_run" not in run_py([TOOL, "--help"], child_env(str(SOURCE))).stdout.split("positional arguments")[0]
