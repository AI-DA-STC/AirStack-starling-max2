"""Replay recorder and renderer (offline visualisation): the recording matches the game, a tiny render works."""
import pathlib
import sys

import numpy as np
import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game import SvgGame  # noqa: E402
from svg_training.core.game_config import TICK_S, load_game_cfg  # noqa: E402
from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN  # noqa: E402
from svg_training.opponents.scripted import make_strategy  # noqa: E402
from svg_training.viz.replay import Scene, frame_indices, record_games, render_replay, result_text  # noqa: E402

CFG = load_game_cfg(use_local=False)[0]


@pytest.fixture(scope="module")
def recs():
    return record_games(CFG, 2, 1, "guard_mark_inside", "strike_flank", num_games=3, seed=3)


def test_recording_shapes_and_arena(recs):
    assert recs, "no game finished"
    for r in recs:
        assert r.pos_m.shape == (r.end_step + 1, 3, 3) and r.alive.shape == (r.end_step + 1, 3)
        assert np.isfinite(r.pos_m).all() and np.abs(r.pos_m).max() < 100      # parked drones are not shown parked
        assert r.alive[0].all() and r.outcome in (GUARD_WIN, STRIKE_WIN)
        assert (np.abs(r.pos_m[..., :2]) <= r.half_m + 1e-5).all()


def test_recording_matches_game_state_and_outcome():
    """Replay the same seeds by hand: positions per step and the outcome equal the recorded ones."""
    n, steps = 2, 1200
    recs = record_games(CFG, 2, 1, "guard_mark_inside", "strike_flank", num_games=n, seed=5)
    game = SvgGame(CFG, n, 2, 1, device="cpu", seed=5, band=1)
    guard = make_strategy("guard_mark_inside", "guard", CFG, n, "cpu", 5 + 101)
    strike = make_strategy("strike_flank", "strike", CFG, n, "cpu", 5 + 202)
    obs = game.reset()
    guard.reset(torch.ones(n, dtype=torch.bool))
    strike.reset(torch.ones(n, dtype=torch.bool))
    by_game = {r.game_index: r for r in recs}
    assert by_game and all(np.allclose(r.pos_m[0], game.pos_m[i].numpy()) for i, r in by_game.items())
    for k in range(1, steps + 1):
        out = game.step({"guard": guard.act(obs["guard"]), "strike": strike.act(obs["strike"])})
        obs = out.obs
        for i, r in by_game.items():
            if k < r.end_step:
                assert np.allclose(r.pos_m[k], game.pos_m[i].numpy(), atol=1e-6)
                assert (r.alive[k] == game.alive[i].numpy()).all()
            elif k == r.end_step:
                assert bool(out.done[i]) and int(out.outcome[i]) == r.outcome
                assert (r.alive[k] == out.info["final_alive"][i].numpy()).all()
        guard.reset(out.done)
        strike.reset(out.done)


def test_texts_and_frames(recs):
    r = recs[0]
    assert result_text(r).startswith(("Guard team holds", "Strike team reaches the zone at t = "))
    idx = frame_indices(r, speed=2, hold_s=1.0, fps=20)
    assert idx[0] == 0 and idx[-1] == r.end_step and len(idx) >= 20
    assert r.end_time_s == pytest.approx(r.end_step * TICK_S)


def test_tiny_render_gif(recs, tmp_path):
    p = render_replay(recs[0], tmp_path / "t.gif", speed=8, hold_s=0.2, size_in=(4, 3), dpi=40)
    assert p.exists() and p.stat().st_size > 1000
    with pytest.raises(ValueError):
        render_replay(recs[0], tmp_path / "t.avi", speed=8, hold_s=0.1, size_in=(4, 3), dpi=30)


def test_every_frame_draws_every_drone_once(recs):
    """Each frame shows G + S markers: a dot for a drone in the game, a cross for one that is out; none is lost."""
    r = max(recs, key=lambda x: x.end_step)
    sc = Scene(r, speed=1, fps=20, trail_s=1.0, size_in=(4, 3), dpi=30, hold_s=0.1)
    n = r.guards + r.strikes
    assert len(sc.dots) == len(sc.crosses) == n
    for j, k in enumerate(sc.idx):
        sc.update(j)
        for m in range(n):
            dot, cross = len(sc.dots[m].get_xdata()), len(sc.crosses[m].get_xdata())
            assert (dot, cross) == ((1, 0) if r.alive[k, m] else (0, 1)), (k, m)
            x, y = (sc.dots[m] if r.alive[k, m] else sc.crosses[m]).get_data()
            assert abs(x[0]) <= r.half_m + 0.1 and abs(y[0]) <= r.half_m + 0.1     # on the drawn arena
        assert sum(len(d.get_xdata()) + len(c.get_xdata()) for d, c in zip(sc.dots, sc.crosses)) == n
    sc.plt.close(sc.fig)


def test_out_drone_is_drawn_as_cross():
    """Force a drop-out: a drone that is out is drawn as a cross where it was last in the game."""
    from svg_training.viz.replay import Recording
    pos = np.zeros((4, 2, 3))
    pos[:, 1, 0] = 1.0
    alive = np.array([[1, 1], [1, 1], [1, 0], [1, 0]], dtype=bool)
    r = Recording(pos, alive, np.zeros(2), 1.0, 5.0, GUARD_WIN, 3, 1, 1, "middle", "pure rules", "a", "b", 0, 0, 2.0)
    sc = Scene(r, 1, 20, 1.0, (4, 3), 30, 0.1)
    sc.update(3)
    assert len(sc.dots[1].get_xdata()) == 0 and list(sc.crosses[1].get_xdata()) == [1.0]
    sc.plt.close(sc.fig)


def test_a_strategy_object_records_as_its_name_does():
    """STE L0.12: ``record_games`` also takes strategy objects (a trained team of either side); a name keeps today's
    path. The same scripts given as objects (seeded as the name path seeds them) record the same games."""
    by_name = record_games(CFG, 2, 1, "guard_mark_inside", "strike_flank", num_games=2, seed=5)
    g = make_strategy("guard_mark_inside", "guard", CFG, 2, "cpu", 5 + 101)
    s = make_strategy("strike_flank", "strike", CFG, 2, "cpu", 5 + 202)
    by_obj = record_games(CFG, 2, 1, g, s, num_games=2, seed=5)
    assert len(by_obj) == len(by_name)
    for a, b in zip(by_obj, by_name):
        assert np.array_equal(a.pos_m, b.pos_m) and a.outcome == b.outcome
        assert a.guard_name == g.name and a.strike_name == s.name


def test_new_clips_carry_a_height_panel_that_follows_the_game(recs):
    """Standing rule (svg_training/CLAUDE.md, videos; VID-1 part 1): a 2-D top-down clip has a height panel. On by
    default; every drone's height up to the frame's step, the height band as dashed lines, a time cursor."""
    from svg_training.viz.replay import Recording
    pos = np.zeros((5, 2, 3))
    pos[:, 0, 2] = [1.2, 1.3, 1.4, 1.5, 1.6]
    pos[:, 1, 2] = 1.2
    alive = np.array([[1, 1], [1, 1], [1, 1], [1, 0], [1, 0]], dtype=bool)
    r = Recording(pos, alive, np.zeros(2), 1.0, 3.0, GUARD_WIN, 4, 1, 1, "lab", "Starling layer", "a", "b", 0, 0, 2.0,
                  height_band_m=(0.5, 1.8))
    sc = Scene(r, 1, 20, 1.0, (4, 3), 30, 0.1)
    assert sc.hax is not None and len(sc.heights) == 2
    sc.update(2)
    t, z = sc.heights[0].get_data()
    assert list(z) == pytest.approx([1.2, 1.3, 1.4]) and list(t) == pytest.approx([0.0, 0.05, 0.1])
    sc.update(4)
    z1 = np.asarray(sc.heights[1].get_data()[1], dtype=float)
    assert np.isnan(z1[3:]).all() and np.isfinite(z1[:3]).all()        # a drone that is out leaves the panel
    assert sorted(round(float(line.get_ydata()[0]), 2) for line in sc.band_lines) == [0.5, 1.8]
    sc.plt.close(sc.fig)
    off = Scene(r, 1, 20, 1.0, (4, 3), 30, 0.1, height_panel=False)
    assert off.hax is None and off.heights == []
    off.plt.close(off.fig)
    assert recs[0].height_band_m == tuple(CFG.arena.height_band_m)       # recorded games carry the band


def test_given_starts_are_played_by_every_slot_and_none_is_unchanged():
    """CLIP-T2 (24 Nov 2026): ``starts`` (starts_m [N, M, 3], miss [N]) makes every slot start there, so two devices whose
    generators draw differently (CPU v CUDA) can play the same games; None keeps the game's own draw, bit for bit."""
    n, seed = 3, 5
    other = SvgGame(CFG, n, 2, 1, device="cpu", seed=seed + 1000, band=1)       # a different draw than seed's own
    given = (other.pos_m.clone(), other.start_miss.clone())
    own = record_games(CFG, 2, 1, "guard_mark_inside", "strike_flank", num_games=n, seed=seed)
    fixed = record_games(CFG, 2, 1, "guard_mark_inside", "strike_flank", num_games=n, seed=seed,
                         starts=given)
    assert fixed and own
    for r in fixed:
        assert np.array_equal(r.pos_m[0], given[0][r.game_index].numpy())
    assert any(not np.array_equal(r.pos_m[0], given[0][r.game_index].numpy()) for r in own)
    again = record_games(CFG, 2, 1, "guard_mark_inside", "strike_flank", num_games=n, seed=seed,
                         starts=None)
    assert [(r.game_index, r.outcome, r.end_step) for r in again] == [(r.game_index, r.outcome, r.end_step) for r in own]
    for a, b in zip(again, own):
        assert np.array_equal(a.pos_m, b.pos_m)


@pytest.mark.parametrize("bad", ["games", "drones", "xyz", "miss"])
def test_given_starts_of_the_wrong_shape_are_refused(bad):
    """CLIP-T2 QC: starts_m [N, M, 3] with N = num_games, M = the game's drones, and miss [N]; anything else refused."""
    n, m = 3, 3
    pos, miss = torch.zeros(n, m, 3), torch.zeros(n, dtype=torch.bool)
    if bad == "games":
        pos = torch.zeros(n + 1, m, 3)
    elif bad == "drones":
        pos = torch.zeros(n, m + 1, 3)
    elif bad == "xyz":
        pos = torch.zeros(n, m, 2)
    else:
        miss = torch.zeros(n + 1, dtype=torch.bool)
    with pytest.raises(ValueError, match="starts"):
        record_games(CFG, 2, 1, "guard_mark_inside", "strike_flank", num_games=n, seed=5, max_steps=2,
                     starts=(pos, miss))


def test_drawn_team_sizes_still_record_without_given_starts():
    """Regression (CLIP-T2 QC): the given-starts hook must not make every drawn-size game refuse (``SvgGame`` refuses a
    subclass that replaces ``_draw_starts`` when sizes are drawn)."""
    cfg = load_game_cfg(ROOT / "configs" / "ste_l2" / "drone_loss_drawn.toml", use_local=False)[0]
    recs = record_games(cfg, 5, 3, "guard_mark_edge", "strike_straight", num_games=2, seed=5, band=0)
    assert recs


def test_given_starts_are_refused_with_drawn_team_sizes():
    """Drawn team sizes start through their own draw (``_sized_starts``), which would ignore given starts silently."""
    cfg = load_game_cfg(ROOT / "configs" / "ste_l2" / "drone_loss_drawn.toml", use_local=False)[0]
    assert cfg.team_size.mode == "drawn"
    with pytest.raises(ValueError, match="given starts"):
        record_games(cfg, 5, 3, "guard_mark_edge", "strike_straight", num_games=2, seed=5, band=0, max_steps=2,
                     starts=(torch.zeros(2, 8, 3), torch.zeros(2, dtype=torch.bool)))


def test_cpu_starts_are_record_games_own_cpu_draw():
    """``cpu_starts``: the starts record_games draws on the CPU (constructor's draw, then reset()'s), on the CPU."""
    from svg_training.viz.replay import cpu_starts
    pos, miss = cpu_starts(CFG, 3, 2, 1, seed=5, band=1)
    assert pos.device.type == "cpu" and pos.shape == (3, 3, 3) and miss.shape == (3,)
    recs = record_games(CFG, 2, 1, "guard_mark_inside", "strike_flank", num_games=3, seed=5)
    assert recs
    for r in recs:
        assert np.array_equal(r.pos_m[0], pos[r.game_index].numpy())
