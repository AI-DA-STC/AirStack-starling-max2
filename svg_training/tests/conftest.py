"""Tests marked ``isaac`` start Isaac Sim (headless, in a subprocess). They are skipped unless SVG_ISAAC_TESTS=1, so the
default suite never starts Isaac Sim (S2b plan D12). Run them after ``scripts/isaac_preflight.sh``:
``docker/run.sh 'SVG_ISAAC_TESTS=1 $SVG_PY -m pytest -q -m isaac'``.

Every test, and every child process it starts, also gets a private shared folder (STE track, task L0.7): the machine's
real one (``<main clone>/svg_training/runs/shared``: the pause log, state.json, the GPU-hour ledger) holds live
process state that cap accounting reads, so no test may read or write it."""
import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def private_shared_folder(tmp_path_factory):
    """``SVG_SHARED_DIR`` under the session's temporary folder, and no legacy pause log read from the real worktrees
    (``SVG_PAUSE_LEGACY_LOGS`` empty); source/svg_training/ste/shared.py and scripts/gpu_pause.sh honour both."""
    patch = pytest.MonkeyPatch()
    patch.setenv("SVG_SHARED_DIR", str(tmp_path_factory.mktemp("svg_shared")))
    patch.setenv("SVG_PAUSE_LEGACY_LOGS", "")
    yield
    patch.undo()


def pytest_collection_modifyitems(config, items):
    if os.environ.get("SVG_ISAAC_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="starts Isaac Sim: set SVG_ISAAC_TESTS=1 after scripts/isaac_preflight.sh")
    for item in items:
        if "isaac" in item.keywords:
            item.add_marker(skip)
