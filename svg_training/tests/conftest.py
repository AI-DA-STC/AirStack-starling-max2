"""Tests marked ``isaac`` start Isaac Sim (headless, in a subprocess). They are skipped unless SVG_ISAAC_TESTS=1, so the
default suite never starts Isaac Sim (S2b plan D12). Run them after ``scripts/isaac_preflight.sh``:
``docker/run.sh 'SVG_ISAAC_TESTS=1 $SVG_PY -m pytest -q -m isaac'``."""
import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("SVG_ISAAC_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="starts Isaac Sim: set SVG_ISAAC_TESTS=1 after scripts/isaac_preflight.sh")
    for item in items:
        if "isaac" in item.keywords:
            item.add_marker(skip)
