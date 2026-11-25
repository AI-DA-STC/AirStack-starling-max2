"""VID-1b: replaying a trained team of L0.12 step by step on T44's starts (CPU only; no Isaac).

The oracle is ``ste/exploit.play_cells``, the function that made each run's evaluation batch: the capture must give the
same per-game numbers bit for bit on the CPU, and its trajectories must be the games of the cells asked for."""
from __future__ import annotations

import numpy as np
import pytest

from svg_training.opponents.scripted import make_strategy
from svg_training.ste import exploit
from svg_training.viz import replay3d as r3

N = 2                        # games per cell (>= 2: a cell index used as a game index is caught)
TICKS = 160


@pytest.fixture(scope="module")
def setup():
    gates = exploit.load_gates()
    ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
    cfg = exploit.variant_cfg(gates, "base")
    cells = exploit.eval_cells(gates, "base", "strike")[:3]       # exploiter, its zero twin, one script
    # a stand-in "trained" Strike team: a script behind the exploiter cell, held 12 ticks like the learner
    stand_in = make_strategy("strike_straight", "strike", cfg, N, "cpu", 7)
    seed = int(ref.meta["seed"])
    keep = [0, 1, 2 * N]                                          # exploiter games 0 and 1, the script cell's game 0
    cap = r3.capture_trained(cfg, "3v3", ref, cells, N, "cpu", seed, TICKS, stand_in, 12, keep)
    stand_in2 = make_strategy("strike_straight", "strike", cfg, N, "cpu", 7)
    oracle = exploit.play_cells(cfg, "3v3", ref, cells, N, "cpu", seed, TICKS, learner=stand_in2, hold_ticks=12)
    return cfg, cells, keep, cap, oracle


def test_trained_capture_equals_play_cells(setup):
    _, _, _, cap, oracle = setup
    for key in ("outcome", "end_step", "tags", "strikes_left", "start_pos_m", "closest_3d_m"):
        np.testing.assert_array_equal(cap.per_game[key], oracle[key], err_msg=key)


def test_trained_trajectories_are_the_asked_games(setup):
    _, _, keep, cap, oracle = setup
    finished = [k for k, g in enumerate(keep) if oracle["end_step"][g] > 0]
    assert finished, "no kept game finished: lengthen TICKS"
    for k in finished:
        g, t = keep[k], cap.trajectories[k]
        assert t.end_step == int(oracle["end_step"][g]) and t.outcome == int(oracle["outcome"][g])
        p, a = t.pos_m[1:].astype(float), t.alive[1:]
        d = np.linalg.norm(p[:, :3, None, :] - p[:, None, 3:, :], axis=-1)
        got = float(np.where(a[:, :3, None] & a[:, None, 3:], d, np.inf).min())
        assert got == pytest.approx(float(oracle["closest_3d_m"][g]), abs=1e-5)
        assert t.tag_radius_m == pytest.approx(1.6)


def test_trained_capture_skips_unfinished_kept_games_only_when_asked(setup):
    cfg, cells, _, _, _ = setup
    gates = exploit.load_gates()
    ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
    still = make_strategy("strike_straight", "strike", cfg, N, "cpu", 7)
    with pytest.raises(RuntimeError, match="did not finish"):
        r3.capture_trained(cfg, "3v3", ref, cells, N, "cpu", int(ref.meta["seed"]), 2, still, 12, [0])


def test_capture_with_players_equals_play_cells_with_players():
    """LS1-M3-T5: ``capture_trained`` passes named ``players`` through to both teams' split as ``play_cells`` does
    (no learner when no cell names the exploiter). A script flown under a prefixed name equals the same script by
    name."""
    gates = exploit.load_gates()
    ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
    cfg = exploit.variant_cfg(gates, "base")
    seed = int(ref.meta["seed"])
    cells = [("guard_mark_edge", "scr:strike_flank"), ("guard_mark_edge", "strike_flank")]

    def named():                                                  # one object per call: a player keeps state
        return {"scr:strike_flank": make_strategy("strike_flank", "strike", cfg, N, "cpu",
                                                  seed + exploit.STRIKE_SEED_OFFSET)}

    keep = [0, N]                                                 # game 0 of each cell
    cap = r3.capture_trained(cfg, "3v3", ref, cells, N, "cpu", seed, TICKS, None, 1, keep, players=named())
    oracle = exploit.play_cells(cfg, "3v3", ref, cells, N, "cpu", seed, TICKS, learner=None, hold_ticks=1,
                                players=named())
    for key in ("outcome", "end_step", "tags", "strikes_left", "start_pos_m", "closest_3d_m"):
        np.testing.assert_array_equal(cap.per_game[key], oracle[key], err_msg=key)
        a = np.asarray(cap.per_game[key])
        np.testing.assert_array_equal(a[:N], a[N:2 * N], err_msg=f"{key}: the named cell and the script's cell")
    assert cap.trajectories[0].end_step == cap.trajectories[1].end_step
    np.testing.assert_array_equal(cap.trajectories[0].pos_m, cap.trajectories[1].pos_m)
