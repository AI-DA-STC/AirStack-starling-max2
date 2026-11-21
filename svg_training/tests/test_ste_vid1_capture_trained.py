"""VID-1b: the capture script's trained-players mode on a small fake L0.12 run folder (CPU only; no Isaac)."""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import numpy as np
import pytest
import torch

from svg_training.ste import exploit
from svg_training.viz import replay3d as r3

ROOT = Path(__file__).resolve().parents[1]
N, TICKS = 2, 160


def _modules(hidden, seed: int) -> dict:
    """agent_final.pt's layout (Learner.modules): per drone the policy and its observation scaler."""
    from skrl.resources.preprocessors.torch import RunningStandardScaler

    from svg_training.opponents.learned import OBS_SPACE, StandinPolicy
    torch.manual_seed(seed)
    out = {}
    for k in range(3):
        pol = StandinPolicy(hidden, "cpu")
        sc = RunningStandardScaler(OBS_SPACE, device="cpu")
        out[f"exploiter_{k}"] = {"policy": pol.state_dict(), "observation_preprocessor": sc.state_dict()}
    return out


@pytest.fixture(scope="module")
def fake_run(tmp_path_factory):
    """A guard-side run of base in the L0.12 layout: gates copy, run.json, agent_final.pt, eval_final.npz (CPU, small)."""
    from svg_training.ste import exploit_train
    root = tmp_path_factory.mktemp("runs")
    rd = root / "2026-11-21_ste_l012_base_guard"
    rd.mkdir()
    gates = exploit.load_gates()
    shutil.copy(gates.path, rd / "gates.toml")
    (rd / "run.json").write_text(json.dumps({"variant": "base", "side": "guard"}))
    mods = _modules(list(gates.trainer["hidden"]), 3)
    torch.save(mods, rd / "agent_final.pt")
    team = exploit_train.team_from_modules("guard", mods, list(gates.trainer["hidden"]), "cpu")
    ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
    pg = exploit.play_cells(exploit.variant_cfg(gates, "base"), "3v3", ref, exploit.eval_cells(gates, "base", "guard"),
                            N, "cpu", int(ref.meta["seed"]), TICKS, learner=team,
                            hold_ticks=int(gates.trainer["decision_ticks"]))
    np.savez(rd / "eval_final.npz", **{k: v for k, v in pg.items() if isinstance(v, np.ndarray)})
    return root, pg


def _main(root, out, *extra):
    spec = importlib.util.spec_from_file_location("ste_vid1_capture", ROOT / "scripts" / "ste_vid1_capture.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main(["--trained-runs-dir", str(root), "--out", str(out), "--runs", "2026-11-21_ste_l012_base_guard",
                     "--device", "cpu", "--games-per-cell", str(N), "--ticks-cap", str(TICKS), *extra])


def test_trained_mode_draws_only_the_record_game(fake_run, tmp_path):
    root, pg = fake_run
    assert _main(root, tmp_path) == 0
    rep = json.loads((tmp_path / "capture_trained.json").read_text())
    row = rep["runs"]["2026-11-21_ste_l012_base_guard"]
    holds = np.flatnonzero(pg["outcome"][:N] == exploit.GUARD_WIN)
    if not holds.size:
        assert row["game_index"] is None and not row["files"]
        return
    assert row["game_index"] == int(holds[0]) and row["game_check"]["equal"] and row["batch_check"]["equal"]
    t = r3.load_trajectory(tmp_path / row["files"][0])
    assert t.meta["kind"] == "trained" and t.meta["side"] == "guard" and t.meta["record"] == "T46"
    assert t.end_step == int(pg["end_step"][row["game_index"]]) and t.outcome == exploit.GUARD_WIN


def test_trained_mode_refuses_a_different_record(fake_run, tmp_path):
    root, pg = fake_run
    bad = tmp_path / "bad"
    shutil.copytree(root, bad)
    rd = bad / "2026-11-21_ste_l012_base_guard"
    d = dict(np.load(rd / "eval_final.npz"))
    d["outcome"] = np.full_like(d["outcome"], exploit.GUARD_WIN)
    d["end_step"] = d["end_step"] + 1                       # every game now differs from the replay
    np.savez(rd / "eval_final.npz", **d)
    assert _main(bad, tmp_path / "o") == 1
    assert not list((tmp_path / "o" / "trajectories").glob("l012_*"))
    (rd / "gates.toml").write_text((rd / "gates.toml").read_text() + "\n# changed\n")
    assert _main(bad, tmp_path / "o2") == 2
