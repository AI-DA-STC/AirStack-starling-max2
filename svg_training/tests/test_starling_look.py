"""STE tasks L0.4 / L0.5: the Starling look plans and the video settings (CPU only; no Isaac).

The plan "painted" must be today's S2b clip look exactly (an "off = identical" test: compat/isaaclab_232 draws the
Starling of every existing clip from this plan); "own_ring" and "own_dot" leave the Starling's own surfaces alone."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from svg_training.viz import starling_look as sl

ROOT = Path(__file__).resolve().parents[1]
GUARD = (0.0, 114 / 255, 178 / 255)


def test_settings_load_and_refuse_unknown_keys(tmp_path):
    s = sl.load_video_settings()
    assert s["look"]["replay_look"] in sl.LOOKS
    assert s["cameras"]["resolution"] == [1280, 720]
    assert s["key_games"]["variants"] == ["base", "tag_1p2", "tag_1p4"]
    bad = (ROOT / "configs" / "ste_video.toml").read_text().replace("[playback]", "[playback]\nsurprise = 1")
    p = tmp_path / "v.toml"
    p.write_text(bad)
    with pytest.raises(KeyError, match="surprise"):
        sl.load_video_settings(p)
    missing = (ROOT / "configs" / "ste_video.toml").read_text().replace("hold_s = 2.0", "")
    p.write_text(missing)
    with pytest.raises(KeyError, match="hold_s"):
        sl.load_video_settings(p)


def test_every_value_line_has_a_status_label():
    for ln in (ROOT / "configs" / "ste_video.toml").read_text().splitlines():
        if "=" in ln and not ln.lstrip().startswith("#"):
            assert any(t in ln for t in ("FIXED", "MEASURED", "PROPOSED", "OPEN")), ln


def test_painted_plan_is_todays_s2b_look_bit_for_bit():
    """Today's constants (compat/isaaclab_232 _add_drone_visuals before L0.5): body (0.22, 0.22, 0.24), rotors in the
    team colour, one sphere of the marker radius r centred 0.12 + r above the body origin."""
    p = sl.look_plan("painted", GUARD, marker_radius_m=0.1)
    assert p.paint == {"body": (0.22, 0.22, 0.24), "rotor0": GUARD, "rotor1": GUARD, "rotor2": GUARD, "rotor3": GUARD}
    assert p.markers == (sl.Marker("sphere", (0.2, 0.2, 0.2), (0.0, 0.0, 0.22), GUARD),)
    assert p.markers[0].casts_shadow                           # the S2b ball casts its shadow, as before
    assert sl.DRONE_BODY_RGB == (0.22, 0.22, 0.24)


def test_own_looks_paint_nothing():
    s = sl.load_video_settings()
    ring = sl.look_plan("own_ring", GUARD, settings=s)
    dot = sl.look_plan("own_dot", GUARD, settings=s)
    assert ring.paint == {} and dot.paint == {}
    (m,) = ring.markers
    assert m.kind == "torus" and m.rgb == GUARD
    r = s["look"]["own_ring"]
    assert m.size_m == (r["major_radius_m"], r["minor_radius_m"], 0.0) and m.xyz_m == (0.0, 0.0, r["z_m"])
    (d,) = dot.markers
    assert d.kind == "cyl" and d.xyz_m[2] == s["look"]["own_dot"]["z_m"]
    assert not m.casts_shadow and not d.casts_shadow            # no marker shadow on the floor (reads as a drone)


def test_ring_clears_the_rotor_tips():
    """The ring's inner edge lies outside every rotor hub plus a 3-inch blade radius (0.038 m)."""
    s = sl.load_video_settings()["look"]["own_ring"]
    hub = max(math.hypot(x, y) for x, y in sl.STARLING_ROTORS_FLU_M)
    assert s["major_radius_m"] - s["minor_radius_m"] > hub + 0.038


def test_look_plan_refuses_unknown_look():
    with pytest.raises(ValueError):
        sl.look_plan("chrome", GUARD, marker_radius_m=0.1)
    with pytest.raises(ValueError):
        sl.look_plan("painted", GUARD)                       # painted needs its marker radius
    with pytest.raises(ValueError):
        sl.look_plan("own_ring", GUARD)                      # own looks need the settings


def test_torus_mesh_geometry():
    pts, counts, idx = sl.torus_mesh(0.25, 0.014, 48, 8)
    assert pts.shape == (48 * 8, 3) and counts.shape == (48 * 8,) and (counts == 4).all()
    assert idx.shape == (48 * 8 * 4,) and idx.min() == 0 and idx.max() == 48 * 8 - 1
    ring = np.hypot(pts[:, 0], pts[:, 1])
    tube = np.hypot(ring - 0.25, pts[:, 2])
    np.testing.assert_allclose(tube, 0.014, atol=1e-12)
    # every vertex is used by exactly four quads (a closed surface)
    assert (np.bincount(idx, minlength=len(pts)) == 4).all()


def test_torus_mesh_refuses_bad_sizes():
    with pytest.raises(ValueError):
        sl.torus_mesh(0.01, 0.02, 48, 8)                     # tube wider than the ring
    with pytest.raises(ValueError):
        sl.torus_mesh(0.25, 0.01, 2, 8)


def test_clip_world_hides_the_physics_box_mesh():
    """L0.4 finding: hiding the typeless "/geometry" prim did nothing (the box was drawn over the Starling in every
    S2b / NUS clip); the compat module must hide the box's own mesh. Source check (the effect is checked in Isaac by
    scripts/ste_l04_clip_drone_still.py; its record is in runs/ste_l04_report.md)."""
    src = (ROOT / "source" / "svg_training" / "compat" / "isaaclab_232.py").read_text()
    assert 'GetPrimAtPath(body + "/geometry/mesh")).MakeInvisible()' in src
    assert 'GetPrimAtPath(body + "/geometry")).MakeInvisible()' not in src


# ------------------------------------------------------------------------------------------------ VID-1b
def test_tag_circle_only_on_guards_at_the_games_radius():
    s = sl.load_video_settings()
    tc = s["look"]["tag_circle"]
    g = sl.look_plan("own_ring", GUARD, settings=s, tag_radius_m=1.4)
    k = sl.look_plan("own_ring", (0.9, 0.4, 0.0), settings=s, tag_radius_m=None)
    assert len(k.markers) == 1                                   # a Strike drone: its ring only
    ring, circle = g.markers
    assert circle.kind == "torus" and circle.size_m[:2] == (1.4, tc["minor_radius_m"]) and not circle.casts_shadow
    assert circle.xyz_m == (0.0, 0.0, 0.0)                       # the Guard's own height: the tag's 3-D slice there
    assert circle.segments == (tc["segments"], tc["tube_segments"])
    f = tc["lighten"]
    assert circle.rgb == pytest.approx(tuple(c + (1 - c) * f for c in GUARD))
    # without a tag radius the plan is the L0.5 plan, unchanged
    assert sl.look_plan("own_ring", GUARD, settings=s).markers == (ring,)


def test_disc_mesh_is_a_true_circle():
    pts, counts, idx = sl.disc_mesh(1.6, 0.02, 128)
    rim = pts[np.abs(np.hypot(pts[:, 0], pts[:, 1]) - 1.6) < 1e-9]
    assert len(rim) == 2 * 128                                   # top and bottom rims on the circle
    assert set(np.round(pts[:, 2], 9)) == {-0.01, 0.01}
    assert idx.min() == 0 and idx.max() == len(pts) - 1 and counts.sum() == len(idx)
    # the polygon's worst gap to the true circle is under 0.5 mm at 1.6 m with 128 sides
    assert 1.6 * (1 - np.cos(np.pi / 128)) < 5e-4
    with pytest.raises(ValueError):
        sl.disc_mesh(1.6, 0.02, 2)


def test_trained_games_settings():
    s = sl.load_video_settings()
    t = s["trained_games"]
    assert t["record"] == "T46" and len(t["runs"]) == 4 and s["arena"]["zone_segments"] >= 64
    import hashlib
    assert t["gates_sha256"] == hashlib.sha256((ROOT / "configs" / "ste_l012" / "gates.toml").read_bytes()).hexdigest()
