"""STE learning track, task L0.7: the one machine-wide folder of live process state (ste/shared.py).

The folder is the same from every worktree: ``SVG_SHARED_DIR`` if set, else ``<main clone>/svg_training/runs/shared``,
the main clone being found through git's common folder. The whole suite runs with ``SVG_SHARED_DIR`` pointed at a
temporary folder (tests/conftest.py), so no test reads or writes the machine's real one."""
import os
import subprocess
from pathlib import Path

import pytest

from _ste_tools import LEGACY_REL, ROOT, SOURCE, make_repo
from _proc import child_env, child_python
from svg_training.ste import shared


def test_the_suite_never_points_at_the_real_shared_folder():
    """tests/conftest.py: every test, and every child process it starts, gets a private shared folder."""
    private = Path(os.environ[shared.SHARED_ENV])
    assert os.environ[shared.LEGACY_LOGS_ENV] == ""
    assert shared.shared_dir(create=False) == private
    real = shared.main_clone() / shared.SHARED_REL
    assert private != real and real not in private.parents
    assert shared.legacy_pause_logs() == ()


def test_env_folder_wins_and_is_created_on_demand(tmp_path, monkeypatch):
    folder = tmp_path / "a" / "shared"
    monkeypatch.setenv(shared.SHARED_ENV, str(folder))
    assert shared.shared_dir(create=False) == folder and not folder.exists()
    assert shared.shared_dir() == folder and folder.is_dir()
    assert shared.pauses_log() == folder / "pauses.log"
    assert shared.state_file() == folder / "state.json"
    assert shared.state_lock() == folder / "state.lock"
    assert shared.gpu_hours_log() == folder / "gpu_hours.log"


def test_default_is_the_main_clones_runs_shared_from_every_worktree(tmp_path, monkeypatch):
    """Without the variable: the same folder from the main clone and from a worktree. In the main clone git prints the
    common folder as a relative ``.git``; in a worktree as an absolute path. Both must give the main clone."""
    main, other = make_repo(tmp_path)
    monkeypatch.delenv(shared.SHARED_ENV)
    expected = main / "svg_training" / "runs" / "shared"
    for start in (main / "svg_training", other / "svg_training", main, other):
        assert shared.main_clone(start) == main, start
        assert shared.shared_dir(create=False, start=start) == expected, start
    assert not expected.exists()
    assert shared.shared_dir(start=other / "svg_training") == expected and expected.is_dir()
    assert set(shared.worktrees(other)) == {main, other} == set(shared.worktrees(main))


def test_this_repository(monkeypatch):
    """The package's own location: the main clone holds a real ``.git`` folder and this worktree is listed."""
    monkeypatch.delenv(shared.SHARED_ENV)
    main = shared.main_clone()
    assert (main / ".git").is_dir()
    assert ROOT.parent in shared.worktrees() and main in shared.worktrees()
    assert shared.shared_dir(create=False) == main / "svg_training" / "runs" / "shared"       # looked up, not created
    ignored = subprocess.run(["git", "check-ignore", "-q", "runs/shared/state.json"], cwd=ROOT)
    assert ignored.returncode == 0, "runs/ must stay git-ignored: the shared folder holds live process state"


def test_outside_a_repository_the_error_names_the_variable(tmp_path, monkeypatch):
    monkeypatch.delenv(shared.SHARED_ENV)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    with pytest.raises(shared.SharedDirError, match="SVG_SHARED_DIR"):
        shared.shared_dir(create=False, start=tmp_path)


def test_legacy_pause_logs_of_every_worktree_and_the_override(tmp_path, monkeypatch):
    """Old copies of gpu_pause.sh write ``<their worktree>/svg_training/runs/nus_port/phase5/pauses.log``."""
    main, other = make_repo(tmp_path)
    monkeypatch.delenv(shared.LEGACY_LOGS_ENV)
    assert set(shared.legacy_pause_logs(other)) == {main / LEGACY_REL, other / LEGACY_REL}
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, os.pathsep.join([str(tmp_path / "x.log"), str(tmp_path / "y.log")]))
    assert shared.legacy_pause_logs(other) == (tmp_path / "x.log", tmp_path / "y.log")
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")
    assert shared.legacy_pause_logs(other) == ()


def test_importing_the_module_runs_no_git_and_loads_no_pytorch(tmp_path):
    """The look-up is lazy: importing costs nothing and works where git is missing (an empty PATH)."""
    code = ("import sys\nimport svg_training.ste.shared as s\n"
            "assert 'torch' not in sys.modules and 'numpy' not in sys.modules\nprint(s.SHARED_ENV)\n")
    env = child_env(str(SOURCE))
    env["PATH"] = str(tmp_path)
    done = subprocess.run([child_python(), "-c", code], env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "SVG_SHARED_DIR"
