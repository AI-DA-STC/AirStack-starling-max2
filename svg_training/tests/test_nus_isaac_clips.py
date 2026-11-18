"""scripts/nus_isaac_clips.py without Isaac: settings, player wiring, game choice, overlay text, and the dry-run/replay passes on a PyTorch rigid-body world."""
from __future__ import annotations

import importlib.util
import json
import tomllib

import numpy as np
import pytest

import _nus_markers  # noqa: F401  (puts source/ and scripts/ on the path)
from _nus_markers import ROOT
from _nus_phase4_fixture import P4_GAMES, build, marker_hangar_value
from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
from svg_training.nus import hangar as hangar_mod, ladder, players

spec = importlib.util.spec_from_file_location("nus_isaac_clips", ROOT / "scripts" / "nus_isaac_clips.py")
clips = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clips)


def test_settings_name_real_players_of_the_right_team():
    settings = clips.load_settings()
    clips.check_clips(settings)
    names = {c["name"] for c in settings["clip"]}
    assert {"g19_vs_s20", "parked_vs_s20", "g19_vs_apf"} <= names
    bad = {"clip": [{"name": "x", "guard": "S20", "strike": "S20"}]}
    with pytest.raises(ValueError):
        clips.check_clips(bad)
    with pytest.raises(KeyError):
        clips.find_clip(settings, "absent")
    assert settings["video"]["gif_max_mb"] <= 2.0


def test_pick_slots_takes_first_win_first_hold_then_makes_up():
    s, g = STRIKE_WIN, GUARD_WIN
    assert clips.pick_slots([s, s, g, s], 2, s, g) == [(0, "strike_win"), (2, "hold")]
    assert clips.pick_slots([s, s, s], 2, s, g) == [(0, "strike_win"), (1, "strike_win")]
    assert clips.pick_slots([g, g, s], 2, s, g) == [(0, "hold"), (2, "strike_win")]
    assert clips.pick_slots([s], 2, s, g) == [(0, "strike_win")]
    assert clips.pick_slots([], 2, s, g) == []


def test_text_and_sidecar_never_carry_the_arena():
    clip = {"name": "n", "guard": "G19", "strike": "S20"}
    line = clips.info_line(clip, 2, 1)
    assert "arena" not in line.lower() and " m" not in line and "G19" in line and "S20" in line
    meta = {"name": "n_hold_1", "commit": "c", "working_tree": "clean", "date": "d", "kind": "hold", "slot": 0, "candidate_games": 1, "row": "6", "seed": 1,
            "result_text": None, "upset": False, "game_length_s": None, "recorded_s": 1.0, "replay_max_pos_diff_m": 0.0, "dry_run_differs": False, "fps": 1,
            "resolution": [1, 1], "hold_s": 0.0, "vram_mib": None, "isaac": "x", "wall_s": 1.0}
    rows = clips.sidecar_rows(clip, meta, 1, 1, None, None, "caption")
    assert not [k for k in rows if "arena" in k or "side" in k or "half" in k]


def test_dry_run_and_replay_agree_on_a_torch_world(tmp_path, monkeypatch):
    from svg_training.models.rigid_body import TorchRigidBodyWorld
    w = build(tmp_path, monkeypatch)
    monkeypatch.setattr(hangar_mod, "LOCAL_HANGAR", w.folder / "nus_hangar.toml")
    monkeypatch.setattr(ladder, "load_starts", lambda path=None: w.starts)
    settings = clips.load_settings()
    ctx = clips.make_context(settings, "cpu", lambda n, m, params, device, geo, guards: TorchRigidBodyWorld(n, m, params.airframe, params.physics_dt_s, device))
    assert ctx.n == P4_GAMES and ctx.row["drone"] == "physics"

    class FakeStage:
        label, taken = "fake", []

        def prepare(self, slot):
            self.taken.append(slot)

        def frame(self):
            return np.zeros((2, 2, 2 + 1), dtype=np.uint8)

        def vram_mib(self):
            return None

    settings["video"]["games_per_clip"] = 1
    stage = FakeStage()
    names = clips.record_clip(ctx, clips.find_clip(settings, "g19_vs_apf"), lambda c: stage, tmp_path / "raw")
    assert len(names) == 1 and stage.taken
    meta = json.loads((tmp_path / "raw" / names[0] / "meta.json").read_text())
    assert (tmp_path / "raw" / names[0] / "raw.mp4").exists()
    assert meta["dry_run_differs"] is False and meta["frames"] == len(meta["per_frame"])
    assert str(marker_hangar_value()) not in json.dumps(meta)
