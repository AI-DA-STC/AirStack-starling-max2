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
