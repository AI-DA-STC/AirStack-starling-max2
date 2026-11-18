"""scripts/nus_isaac_clips.py without Isaac: settings, player wiring, game choice, overlay text, and the dry-run/replay passes on a PyTorch rigid-body world."""
from __future__ import annotations

import importlib.util
import types
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


# ------------------------------------------------------------------------------------------------ second set (18 Nov evening): scenes, chosen kinds, captions
NUS_CAPTION = "NUS's converted policy, Isaac Lab Starlings, tier 2"
BACKDROP_CAPTION = "backdrop only: drones do not see or avoid the objects"


def test_defaults_unchanged_for_the_first_set():
    settings = clips.load_settings()
    for name in ("g19_vs_s20", "parked_vs_s20", "g19_vs_apf"):
        clip = clips.find_clip(settings, name)
        assert clips.scene_of(clip) == "plain" and clips.caption_of(settings, clip) == settings["video"]["caption"]
        assert "kinds" not in clip and "candidate_games" not in clip
    clip = {"name": "n", "guard": "G19", "strike": "S20"}
    assert clips.info_line(clip, 2, 1) == "2 Guard v 1 Strike drones | Guard: G19, Strike: S20"


def test_new_clips_say_whose_policy_and_that_the_backdrop_is_visual_only():
    settings = clips.load_settings()
    new = [c for c in settings["clip"] if "caption" in c]
    scenes = {clips.scene_of(c) for c in new}
    assert {"plain", "props", "construction_site"} <= scenes
    for clip in new:
        caption = clips.caption_of(settings, clip)
        assert NUS_CAPTION in caption, clip["name"]
        assert (BACKDROP_CAPTION in caption) == (clips.scene_of(clip) != "plain"), clip["name"]
        assert "validated" not in caption.lower()
    for clip in settings["clip"]:
        assert clips.scene_of(clip) == "plain" or "caption" in clip, clip["name"]


def test_clip_names_do_not_prefix_one_another():           # encode() finds a clip's takes by the "<name>_" prefix
    names = [c["name"] for c in clips.load_settings()["clip"]]
    assert len(set(names)) == len(names)
    assert not [(a, b) for a in names for b in names if a != b and b.startswith(a + "_")]


def test_check_clips_takes_scripted_players_of_the_right_team_and_checks_scenes():
    ok = {"clip": [{"name": "x", "guard": "guard_mirror", "strike": "S20"}, {"name": "y", "guard": "G19", "strike": "strike_flank"}]}
    clips.check_clips(ok)
    for bad in ({"name": "x", "guard": "strike_flank", "strike": "S20"},
                {"name": "x", "guard": "G19", "strike": "S20", "scene": "moon"},
                {"name": "x", "guard": "G19", "strike": "S20", "scene": "props"},                       # props need a seed and a count
                {"name": "x", "guard": "G19", "strike": "S20", "kinds": ["draw"]}):
        with pytest.raises(ValueError):
            clips.check_clips({"clip": [bad]})


def test_pick_kinds_takes_the_first_unused_game_of_each_kind():
    s, g = STRIKE_WIN, GUARD_WIN
    assert clips.pick_kinds([s, s, g, s], ["hold"], s, g) == [(2, "hold")]
    assert clips.pick_kinds([s, g, s], ["strike_win", "strike_win"], s, g) == [(0, "strike_win"), (2, "strike_win")]
    assert clips.pick_kinds([g, s], ["strike_win", "hold"], s, g) == [(0, "hold"), (1, "strike_win")]
    assert clips.pick_kinds([s, s], ["hold"], s, g) == []


def test_info_line_and_sidecar_name_the_world_but_never_the_arena():
    clip = {"name": "n", "guard": "G19", "strike": "S20", "scene": "props", "props_seed": 1, "props_count": 2}
    line = clips.info_line(clip, 2, 1)
    assert line.startswith("2 Guard v 1 Strike drones | Guard: G19, Strike: S20") and "props" in line and "arena" not in line.lower()
    meta = {"name": "n_hold_1", "commit": "c", "working_tree": "clean", "date": "d", "kind": "hold", "slot": 0, "candidate_games": 1, "row": "6", "seed": 1,
            "result_text": None, "upset": False, "game_length_s": None, "recorded_s": 1.0, "replay_max_pos_diff_m": 0.0, "dry_run_differs": False, "fps": 1,
            "resolution": [1, 1], "hold_s": 0.0, "vram_mib": None, "isaac": "x", "wall_s": 1.0, "scene": "props",
            "scene_detail": {"props_count": 2, "backdrop_file": None, "backdrop_sha256": None}}
    rows = clips.sidecar_rows(clip, meta, 1, 1, None, None, "caption")
    assert rows["scene"] == "props" and rows["props_count"] == 2
    assert not [k for k in rows if "arena" in k or "side" in k or "half" in k]
    plain = {k: v for k, v in meta.items() if k not in ("scene", "scene_detail")}
    assert "scene" not in clips.sidecar_rows({"name": "n", "guard": "G19", "strike": "S20"}, plain, 1, 1, None, None, "caption")


def _run_main(monkeypatch, argv, preflight_code):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return types.SimpleNamespace(returncode=preflight_code, stdout="", stderr="")
    monkeypatch.setattr(clips.subprocess, "run", fake_run)
    monkeypatch.setattr(clips.sys, "argv", ["nus_isaac_clips.py", *argv])
    return clips.main(), calls


def test_site_clip_without_the_world_file_stops_before_isaac(tmp_path, monkeypatch):
    scenes = tmp_path / "scenes.toml"
    scenes.write_text('[construction_site]\nusd = "absent/construction_site_full.usdc"\n')
    monkeypatch.setattr(clips, "SCENES", scenes)
    site = next(c["name"] for c in clips.load_settings()["clip"] if clips.scene_of(c) == "construction_site")
    code, calls = _run_main(monkeypatch, ["--clip", site, "--out", str(tmp_path / "out")], 0)
    assert code == clips.EXIT_BAD_ARGS and calls == []


def test_allow_siblings_reaches_the_preflight_only_when_asked(tmp_path, monkeypatch):
    busy = clips.EXIT_BAD_ARGS + clips.EXIT_BAD_ARGS + clips.EXIT_CRASH      # any non-zero preflight code is passed on
    code, calls = _run_main(monkeypatch, ["--clip", "g19_vs_s20", "--out", str(tmp_path)], busy)
    assert code == busy and "--allow-siblings" not in calls[0] and "--approved-headless" in calls[0]
    code, calls = _run_main(monkeypatch, ["--clip", "g19_vs_s20", "--out", str(tmp_path), "--allow-siblings"], busy)
    assert code == busy and "--allow-siblings" in calls[0]


def test_first_start_offsets_the_candidates_into_the_paired_starts(tmp_path, monkeypatch):
    from svg_training.models.rigid_body import TorchRigidBodyWorld
    w = build(tmp_path, monkeypatch)
    monkeypatch.setattr(hangar_mod, "LOCAL_HANGAR", w.folder / "nus_hangar.toml")
    monkeypatch.setattr(ladder, "load_starts", lambda path=None: w.starts)
    make = lambda n, m, params, device, geo, guards: TorchRigidBodyWorld(n, m, params.airframe, params.physics_dt_s, device)  # noqa: E731
    ctx = clips.make_context(clips.load_settings(), "cpu", make, games=P4_GAMES, first=1)
    assert ctx.n == P4_GAMES - 1 and ctx.first == 1
    assert bool((ctx.starts["starts_units"] == w.starts["starts_units"][1:]).all())
    clip = {"name": "n", "guard": "G19", "strike": "S20", "first_start": 2}
    meta = {"name": "n_hold_1", "commit": "c", "working_tree": "clean", "date": "d", "kind": "hold", "slot": 1, "candidate_games": 1, "row": "6", "seed": 1,
            "result_text": None, "upset": False, "game_length_s": None, "recorded_s": 1.0, "replay_max_pos_diff_m": 0.0, "dry_run_differs": False, "fps": 1,
            "resolution": [1, 1], "hold_s": 0.0, "vram_mib": None, "isaac": "x", "wall_s": 1.0, "first_start": 2}
    assert clips.sidecar_rows(clip, meta, 1, 1, None, None, "c")["paired_start_index"] == 2 + 1
