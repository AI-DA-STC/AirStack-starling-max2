"""VID-1 part 2: the data path of the 3-D replay (CPU only; no Isaac).

The capture re-plays one L0.11 batch exactly as ``ste/sweep.play_batch`` plays it and keeps every step of chosen games;
its per-game numbers must equal play_batch's bit for bit (the oracle), and the check against a record must catch a
difference. Then: the trajectory file, the key-game rule, both cameras, the playback maths and the captions."""
from __future__ import annotations

import json

import numpy as np
import pytest

from svg_training.bench.overlay import FRAME_BOX, project
from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
from svg_training.ste import sweep
from svg_training.viz import replay3d as r3

CELLS = (("guard_mark_edge", "strike_straight"), ("guard_mirror", "strike_low"))
GAMES = 3


@pytest.fixture(scope="module")
def small():
    gates = sweep.load_gates()
    cfg = sweep.variant_cfg(gates, "base")
    run = {**gates.run, "games_per_cell": GAMES, "device": "cpu", "ticks_cap": 400}
    keep = [0, GAMES + 1]                                   # game 0 of cell 0, game 1 of cell 1
    cap = r3.capture_batch(cfg, "3v3", CELLS, run, keep)
    oracle = sweep.play_batch(cfg, "3v3", CELLS, run)
    return cfg, run, keep, cap, oracle


def test_capture_equals_play_batch(small):
    _, _, _, cap, oracle = small
    for key in r3.EXACT_KEYS:
        np.testing.assert_array_equal(cap.per_game[key], oracle.per_game[key], err_msg=key)


def test_trajectory_matches_the_game(small):
    cfg, _, keep, cap, oracle = small
    for k, g in enumerate(keep):
        t = cap.trajectories[k]
        end = int(oracle.per_game["end_step"][g])
        assert t.end_step == end and t.pos_m.shape == (end + 1, 6, 3) and t.alive.shape == (end + 1, 6)
        assert t.outcome == int(oracle.per_game["outcome"][g])
        np.testing.assert_array_equal(t.pos_m[0], oracle.per_game["start_pos_m"][g])
        assert t.alive[0].all()
        assert np.abs(t.pos_m).max() < 10.0                  # drones out are shown where they were, never parked
        tags = int(oracle.per_game["tags"][g])
        assert int((~t.alive[-1, 3:]).sum()) == tags          # Strike drones out at the end = Strike drones tagged
        if t.outcome == STRIKE_WIN:
            d = np.linalg.norm(t.pos_m[-1, 3:, :2] - t.zone_centre_m, axis=-1)
            assert (d[t.alive[-1, 3:]] <= t.zone_radius_m + 1e-6).any()
        lo, hi = t.height_band_m
        z = t.pos_m[..., 2][t.alive]
        assert z.min() >= lo - 1e-5 and z.max() <= hi + 1e-5
        assert t.half_m == pytest.approx(3.25) and t.wall_margin_m == pytest.approx(0.25)   # base: 6.5 m lab arena
        # every later frame belongs to game g (starts are tiled over the cells, so frame 0 cannot tell a wrong cell
        # index): the closest live Guard-Strike 3-D distance over frames 1..end equals the oracle's for game g
        p, a = t.pos_m[1:].astype(float), t.alive[1:]
        d = np.linalg.norm(p[:, :3, None, :] - p[:, None, 3:, :], axis=-1)           # [T, G, S]
        live = a[:, :3, None] & a[:, None, 3:]
        got = float(np.where(live, d, np.inf).min())
        assert got == pytest.approx(float(oracle.per_game["closest_3d_m"][g]), abs=1e-5)


def test_check_against_record(small):
    _, _, _, cap, oracle = small
    rec = {k: np.array(v) for k, v in oracle.per_game.items()}
    ok = r3.check_against_record(cap.per_game, rec)
    assert ok["equal"] and all(v == 0 for v in ok["mismatches"].values())
    rec["end_step"][1] += 1
    bad = r3.check_against_record(cap.per_game, rec)
    assert not bad["equal"] and bad["mismatches"]["end_step"] == 1


def test_check_compares_closest_approach_within_tolerance(small):
    """As the sweep's same-seed control: closest 3-D and horizontal approach within tol_m (inf equals inf)."""
    _, _, _, cap, oracle = small
    rec = {k: np.array(v) for k, v in oracle.per_game.items()}
    for key in ("closest_3d_m", "closest_m"):
        assert key in cap.per_game
    rec["closest_3d_m"][0] += 1e-4
    assert r3.check_against_record(cap.per_game, rec, tol_m=1e-3)["equal"]
    bad = r3.check_against_record(cap.per_game, rec, tol_m=1e-5)
    assert not bad["equal"] and bad["mismatches"]["closest_3d_m"] == 1


def test_capture_refuses_a_surviving_guard(small):
    """The banner and the crosses assume 1-for-1 tags: a game where a tagged Guard may survive is refused."""
    cfg, run, _, _, _ = small
    with pytest.raises(ValueError, match="guard_survives_tag_prob"):
        r3.capture_batch(cfg.replace(**{"tag.guard_survives_tag_prob": 1.0}), "3v3", CELLS, run, [0])


def test_capture_passes_the_strike_start_offset(small):
    cfg, run, _, _, _ = small
    cap = r3.capture_batch(cfg, "3v3", CELLS[:1], {**run, "ticks_cap": 2}, [], strike_start_dz_m=0.001)
    oracle = sweep.play_batch(cfg, "3v3", CELLS[:1], {**run, "ticks_cap": 2}, strike_start_dz_m=0.001)
    np.testing.assert_array_equal(cap.per_game["start_pos_m"], oracle.per_game["start_pos_m"])


def test_trajectory_file_round_trip(small, tmp_path):
    t = small[3].trajectories[0]
    t.meta.update({"variant": "base", "game_index": 0})
    p = r3.save_trajectory(tmp_path / "base_hold", t)
    assert p.suffix == ".npz" and p.with_suffix(".json").is_file()
    u = r3.load_trajectory(p)
    for f in ("pos_m", "alive", "yaw_rad", "zone_centre_m"):
        np.testing.assert_array_equal(getattr(u, f), getattr(t, f))
    assert (u.outcome, u.end_step, u.guards, u.strikes, u.meta) == (t.outcome, t.end_step, t.guards, t.strikes, t.meta)
    json.loads(p.with_suffix(".json").read_text())


def test_load_refuses_bad_shapes(small, tmp_path):
    t = small[3].trajectories[0]
    p = r3.save_trajectory(tmp_path / "x", t)
    d = dict(np.load(p))
    d["alive"] = d["alive"][:-1]
    np.savez(p, **d)
    with pytest.raises(ValueError, match="alive"):
        r3.load_trajectory(p)


def test_key_game_rule():
    out = np.array([GUARD_WIN, GUARD_WIN, STRIKE_WIN, GUARD_WIN, STRIKE_WIN], dtype=np.int8)
    assert r3.pick_key_games(out, ["hold", "reach"]) == {"hold": 0, "reach": 2}
    assert r3.pick_key_games(np.full(4, GUARD_WIN, np.int8), ["hold", "reach"]) == {"hold": 0, "reach": None}
    with pytest.raises(ValueError):
        r3.pick_key_games(out, ["draw"])


def test_cell_index_in_its_batch():
    gates = sweep.load_gates()
    plan = sweep.build_plan(gates)
    batch_id, cells, i = r3.find_cell(gates, plan, "base", ("guard_mark_edge", "strike_straight"))
    assert batch_id == "base/b00" and cells[i] == ("guard_mark_edge", "strike_straight")
    with pytest.raises(KeyError):
        r3.find_cell(gates, plan, "base", ("guard_mark_edge", "strike_nothing"))


def _inside(p):
    return (np.isfinite(p).all() and FRAME_BOX["x"][0] <= p[:, 0].min() and p[:, 0].max() <= FRAME_BOX["x"][1]
            and FRAME_BOX["y"][0] <= p[:, 1].min() and p[:, 1].max() <= FRAME_BOX["y"][1])


def _arena_points(half, top):
    return np.array([[sx * half, sy * half, z] for sx in (-1, 1) for sy in (-1, 1) for z in (0.0, top)])


@pytest.mark.parametrize("half", [3.25, 3.75])
def test_top_camera_frames_the_arena_north_up(half):
    eye, look = r3.top_view_pose(half, top_m=1.8, tilt_deg=2.0, wall_margin_m=0.25)
    outline = r3.arena_outline_m(half, 1.8, 0.25)
    assert _inside(project(outline, eye, look)) and _inside(project(_arena_points(half - 0.25, 1.8), eye, look))
    d = np.subtract(look, eye)
    off_vertical = np.degrees(np.arccos(-d[2] / np.linalg.norm(d)))
    assert off_vertical == pytest.approx(2.0, abs=1e-6)
    north, south = project(np.array([[0.0, 2.0, 0.0], [0.0, -2.0, 0.0]]), eye, look)
    east = project(np.array([[2.0, 0.0, 0.0]]), eye, look)[0]
    assert north[1] > 0 > south[1] and east[0] > 0                # north at the top, east on the right
    # tight: 10 % closer and the arena no longer fits
    e2 = tuple(np.asarray(look) + 0.9 * (np.asarray(eye) - np.asarray(look)))
    assert not _inside(project(outline, e2, look))


def test_top_camera_refuses_vertical():
    with pytest.raises(ValueError):
        r3.top_view_pose(3.25, top_m=1.8, tilt_deg=0.0)


def test_both_cameras_keep_the_game_in_frame(small):
    t = small[3].trajectories[0]
    for eye, look in r3.camera_poses(t.half_m, t.height_band_m[1], tilt_deg=2.0, perspective_view="wide",
                                     wall_margin_m=t.wall_margin_m):
        assert _inside(project(t.pos_m[t.alive], eye, look))


def test_playback_maths():
    assert r3.playback_fps(0.5) == 10 and r3.playback_fps(1.0) == 20
    with pytest.raises(ValueError):
        r3.playback_fps(0.33)                                      # not a whole number of frames per second
    assert r3.hold_frames(2.0, 10) == 20


def test_outcome_and_caption_text():
    assert r3.outcome_text(STRIKE_WIN, 54, 1, 2) == "Strike team reaches the zone at 2.7 s"
    assert r3.outcome_text(GUARD_WIN, 56, 3, 0) == "Guard team holds: 3-for-3 tags, no Guard left"
    assert r3.outcome_text(GUARD_WIN, 56, 2, 1) == "Guard team holds: 2-for-2 tags, 1 Guard left"
    cap = r3.caption("tag_1p2", 0.5)
    assert len(cap) <= 400 and "training simulator" in cap.lower() and "not a flight" in cap
    assert "0.5x real time" in cap
    info = r3.info_line("base", 3, 3, "guard_mark_edge", "strike_straight", 17, 6.5)
    assert "mark edge" in info and "game 17" in info and "6.5 m" in info


def test_label_pixels():
    eye, look = (0.0, -10.0, 5.0), (0.0, 0.0, 0.0)
    px = r3.to_pixels(np.array([[0.0, 0.0, 0.0]]), eye, look, (1280, 720))
    assert px.shape == (1, 2) and abs(px[0, 0] - 640) < 1e-6 and abs(px[0, 1] - 360) < 1e-6


def test_tagged_marks_from_the_tick_out():
    """Crosses at the last in-game place of every drone that is out, from the tick it is out (one per drone)."""
    pos = np.zeros((4, 3, 3))
    pos[:, :, 0] = [[0, 1, 2]] * 4
    alive = np.ones((4, 3), bool)
    alive[2:, 1] = False
    assert r3.tagged_marks(pos, alive, 1) == []
    marks = r3.tagged_marks(pos, alive, 3)
    assert [(m, tuple(p)) for m, p in marks] == [(1, (1.0, 0.0, 0.0))]


def test_cell_counts():
    out = np.array([GUARD_WIN] * 7 + [STRIKE_WIN] * 3, dtype=np.int8)
    assert r3.cell_counts(out) == {"games": 10, "holds": 7, "reaches": 3}
