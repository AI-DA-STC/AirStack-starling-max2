"""VID-1 part 2: the capture script on a small fake record in the T44 layout (CPU only; no Isaac)."""
from __future__ import annotations

import json

import numpy as np
import pytest

from svg_training.ste import sweep
from svg_training.viz import replay3d as r3

# ------------------------------------------------------------------------------------------------ the capture script
@pytest.fixture(scope="module")
def fake_record(tmp_path_factory):
    """A small record in the T44 layout: the gate file copy, results.json's shortlist rows, the base batch's cell file
    (1 game per cell, 120 ticks, CPU)."""
    import shutil

    root = tmp_path_factory.mktemp("rec")
    gates = sweep.load_gates()
    shutil.copy(gates.path, root / "gates.toml")
    run = {**gates.run, "games_per_cell": 1, "device": "cpu", "ticks_cap": 120}
    plan = sweep.build_plan(gates)
    _, cells, _ = r3.find_cell(gates, plan, "base", ("guard_mark_edge", "strike_straight"))
    res = sweep.play_batch(sweep.variant_cfg(gates, "base"), "3v3", cells, run)
    (root / "cells").mkdir()
    np.savez(root / "cells" / "base__b00.npz", **res.per_game)
    (root / "results.json").write_text(json.dumps({"shortlist": {"variants": [
        {"variant": "base", "g_star": "guard_mark_edge", "s_star": "strike_straight"}]}}))
    return root


def _capture(rec, out, *extra):
    import importlib.util

    spec = importlib.util.spec_from_file_location("ste_vid1_capture", r3.Path(__file__).resolve().parents[1]
                                                  / "scripts" / "ste_vid1_capture.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main(["--record-run-dir", str(rec), "--out", str(out), "--variants", "base", "--device", "cpu",
                     "--games-per-cell", "1", "--ticks-cap", "120", *extra])


def test_capture_script_writes_checked_trajectories(fake_record, tmp_path):
    assert _capture(fake_record, tmp_path) == 0
    rep = json.loads((tmp_path / "capture.json").read_text())
    row = rep["variants"]["base"]
    assert row["check"]["equal"] and row["games_compared"] == 30 and rep["overrides"]["games_per_cell"] == 1
    assert len(row["files"]) == 1                    # one game per cell: one outcome
    for f in row["files"]:
        t = r3.load_trajectory(tmp_path / f)
        assert t.meta["variant"] == "base" and t.meta["guard"] == "guard_mark_edge"
        assert t.meta["outcome_name"] in ("hold", "reach") and t.meta["record"] == "T44"
        assert t.meta["games_per_cell"] == 1


def test_capture_script_refuses_a_different_record(fake_record, tmp_path):
    import shutil

    bad = tmp_path / "bad"
    shutil.copytree(fake_record, bad)
    d = dict(np.load(bad / "cells" / "base__b00.npz"))
    d["tags"] = d["tags"] + 1
    np.savez(bad / "cells" / "base__b00.npz", **d)
    assert _capture(bad, tmp_path / "o1") == 1
    assert not (tmp_path / "o1" / "trajectories").exists()
    (bad / "gates.toml").write_text((bad / "gates.toml").read_text() + "\n# changed\n")
    assert _capture(bad, tmp_path / "o2") == 2
