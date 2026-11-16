"""S2b Task 6: the video overlay, the clip rule, the clip settings and the pure helpers of the video script (CPU only;
no Isaac). The clips themselves are made on the host by scripts/make_s2b_video.py (headless, cameras on)."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import numpy as np
import pytest

from svg_training.bench.overlay import (camera_pose, draw_overlay, encode_gif, encode_mp4, pick_clip_slot,
                                        place_props, project, wrap_caption)
from svg_training.core.game_config import load_s2b_gates

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "make_s2b_video.py"
SCENES = ROOT / "configs" / "s2b_video_scenes.toml"
CAPTION = "Training simulator (Isaac Lab), scripted strategies, not a real flight"
LEGEND = {"Guard team": (0, 114, 178), "Strike team": (230, 159, 0)}


def test_overlay_draws_caption():
    f = draw_overlay(np.zeros((720, 1280, 3), np.uint8), CAPTION, LEGEND, 12.3, None)
    assert f[-60:, :, :].max() > 0 and f.shape == (720, 1280, 3)        # caption band is drawn


def test_overlay_leaves_input_and_shows_outcome():
    frame = np.zeros((720, 1280, 3), np.uint8)
    a = draw_overlay(frame, CAPTION, LEGEND, 12.3, None)
    b = draw_overlay(frame, CAPTION, LEGEND, 12.3, "Guard team holds the zone")
    assert frame.max() == 0                                              # a copy is drawn on, not the input
    assert a.dtype == np.uint8 and (b != a).any()                        # the outcome banner adds pixels
    top = slice(60, 160)
    assert (b[top] != a[top]).any()                                      # ... near the top, under the clock


def test_overlay_wraps_a_long_caption():
    long = ("Training simulator (Isaac Lab): scripted strategies, the construction site is a backdrop only - the "
            "drones do not see or avoid the buildings yet; not a real flight")
    lines = wrap_caption(long, 1280)
    assert len(lines) >= 2 and " ".join(lines) == long
    f = draw_overlay(np.zeros((720, 1280, 3), np.uint8), long, LEGEND, 3.0, None)
    assert f[-60:].max() > 0 and f[-130:-60].max() > 0                   # two caption lines, both drawn


def test_pick_clip_slot_rule():
    assert pick_clip_slot(np.array([12.0, 25.0, 33.0, 50.0]), 20, 40) == 1
    assert pick_clip_slot(np.array([5.0, 8.0, 12.0, 15.0]), 20, 40) == 3   # none in range: the longest


def test_pick_clip_slot_ties_take_the_first():
    assert pick_clip_slot(np.array([60.0, 60.0, 60.0]), 20, 40) == 0       # every game held to time-out


def test_video_config_caption_and_no_local():
    v = load_s2b_gates()["video"]
    assert "not a real flight" in v["caption"] and v["max_mb"] <= 10
    src = SCRIPT.read_text()
    assert "use_local=False" in src and "--local-dir" not in src and "configs/local" not in src


def test_scene_clips_captions_say_what_the_drones_do_not_see():
    sc = tomllib.loads(SCENES.read_text())
    names = {c["name"] for c in load_s2b_gates()["video"]["clips"]}
    for c in sc["clips"]:
        assert c["name"] not in names                                    # no clash with the four plan clips
        assert c["scene"] in ("props", "construction_site")
        assert "not a real flight" in c["caption"] and len(c["caption"]) <= 400
        assert "do not see or avoid" in c["caption"]
    site = [c for c in sc["clips"] if c["scene"] == "construction_site"]
    assert site and all(c["band"] in ("lab", "middle") for c in site)    # the clear patch holds lab and middle only
    assert sc["construction_site"]["clear_radius_m"] >= 5.0 * 2 ** 0.5   # a middle arena's corners fit


def test_place_props_is_seeded_and_keeps_out_of_the_zone():
    centre, radius, half = np.array([1.0, -0.5]), 1.2, 4.0
    a = place_props(7, half, centre, radius, count=10)
    b = place_props(7, half, centre, radius, count=10)
    assert [p["kind"] for p in a] == [p["kind"] for p in b] and np.allclose([p["xy_m"] for p in a],
                                                                             [p["xy_m"] for p in b])
    for p in a:
        xy = np.asarray(p["xy_m"])
        assert np.abs(xy).max() + p["size_m"][0] / 2 <= half                  # inside the arena
        assert np.linalg.norm(xy - centre) >= radius + 0.5                     # clear of the zone
        assert p["kind"] in ("block", "column") and p["size_m"][2] > 0
    assert {p["kind"] for p in a} == {"block", "column"}


def test_camera_pose_frames_the_arena():
    o = np.array([10.0, 20.0, 0.0])
    for view in ("wide", "high"):
        for half in (2.0, 5.0, 8.0):
            eye, look = camera_pose(half, origin_m=o, view=view)
            assert eye[2] > look[2]                                           # above the arena
            corners = np.array([[sx * half, sy * half, z] for sx in (-1, 1) for sy in (-1, 1) for z in (0, 1.8)]) + o
            p = project(corners, eye, look)
            assert np.isfinite(p).all()
            assert -0.95 < p[:, 0].min() and p[:, 0].max() < 0.95                # inside the frame, left-right
            assert -0.67 < p[:, 1].min() and p[:, 1].max() < 0.81                # clear of caption band and clock
            assert max(np.abs(p[:, 0]).max(), p[:, 1].max(), -p[:, 1].min()) > 0.55   # and not tiny


def test_encoders_respect_the_size_cap(tmp_path):
    rng = np.random.default_rng(0)
    frames = [rng.integers(0, 255, (180, 320, 3), dtype=np.uint8) for _ in range(30)]   # noise: hard to compress
    mp4, crf = encode_mp4(frames, tmp_path / "x.mp4", fps=20, max_mb=0.2)
    assert mp4.stat().st_size <= 0.2e6 and crf >= 23
    gif, info = encode_gif(frames, tmp_path / "x.gif", fps=10, max_mb=0.5)
    assert gif.stat().st_size <= 0.5e6 and info["width"] <= 320


def test_script_imports_isaac_only_inside_functions():
    src = SCRIPT.read_text()
    assert not re.search(r"^(from|import) (isaaclab\w*|isaacsim\w*|omni\w*|pxr)", src, re.M)


@pytest.mark.parametrize("name", ["s2b_2v1_lab", "s2b_5v3_middle"])
def test_plan_clips_exist_in_config(name):
    assert name in {c["name"] for c in load_s2b_gates()["video"]["clips"]}


def test_sidecar_working_tree_is_the_recording_time_state():   # fix round 1: never the encode-time tree
    import importlib.util
    spec = importlib.util.spec_from_file_location("make_s2b_video", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.recorded_working_tree({"working_tree": "clean"}) == "clean"
    assert mod.recorded_working_tree({}) == "unknown (not recorded at recording time)"
    assert "working_tree_state()" not in SCRIPT.read_text().split("def write_sidecar", 1)[1]
