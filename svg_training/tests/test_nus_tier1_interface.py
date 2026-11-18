"""Phase 5 Task S2: the interface.toml of a stage 5.2 checkpoint (policy interface v0.2), CPU, marker local files. No numeric literal (G2)."""
from __future__ import annotations

import tomllib

import pytest

import _nus_markers  # noqa: F401  (puts source/ on the path)
from _nus_phase4_fixture import build
from svg_training.core.observations import OBS_DIM_V02
from svg_training.nus import outputs
from svg_training.nus.tier1_interface import TIER1_INTERFACE_KEYS, build_tier1_interface, write_tier1_interface

COMMIT = "a" * (len("0123456789abcdef") * 2 + len("01234567"))   # a 40-character hash


def _data(w, team="guard"):
    return build_tier1_interface(team=team, cfg=w.cfg("5"), guards=w.guards, strikes=w.strikes, decision_ticks=w.geo.hold_ticks,
                                 game_config=w.folder / "game.toml", game_config_sha256="g", params_sha256="p",
                                 local_sha256={"rules": "r", "deploy": "d"}, compute_dtype="float32", source_commit=COMMIT, seed=1,
                                 generation=1, checkpoint_sha256="c")


def test_interface_v02_keys_and_values(tmp_path, monkeypatch):
    w = build(tmp_path, monkeypatch)
    monkeypatch.setattr(outputs, "RUNS_DIR", tmp_path / "runs")
    path = write_tier1_interface(tmp_path / "runs" / "x" / "interface.toml", _data(w))
    data = tomllib.loads(path.read_text())
    assert tuple(data) == TIER1_INTERFACE_KEYS
    assert data["interface_version"] == "0.2" and data["observation_width"] == OBS_DIM_V02
    assert data["team"] == "guard" and data["yaw_rate"] == 0 and data["decision_ticks"] == w.geo.hold_ticks
    assert data["team_speed_mps"] == pytest.approx(w.cfg("5").team_speed_mps("guard"))
    assert "EXPLORATORY" in data["drone_model_status"] and "training simulator" in data["simulator"]


def test_interface_refuses_outside_runs_a_bad_team_and_a_short_commit(tmp_path, monkeypatch):
    w = build(tmp_path, monkeypatch)
    monkeypatch.setattr(outputs, "RUNS_DIR", tmp_path / "runs")
    with pytest.raises(ValueError):
        write_tier1_interface(tmp_path / "elsewhere" / "interface.toml", _data(w))
    with pytest.raises(ValueError):
        _data(w, team="both")
    with pytest.raises(ValueError):
        build_tier1_interface(**{**dict(team="guard", cfg=w.cfg("5"), guards=w.guards, strikes=w.strikes, decision_ticks=1,
                                        game_config=w.folder, game_config_sha256="g", params_sha256="p", local_sha256={},
                                        compute_dtype="float32", source_commit="abc", seed=1, generation=1, checkpoint_sha256="c")})
